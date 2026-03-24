# Testing

## Running Tests

Tests run outside Docker, directly in the project's venv.

### CLI tests

```bash
# Run the CLI test suite
pytest phoxtail/cli/tests/ -p no:django

# Run a specific test file
pytest phoxtail/cli/tests/test_config.py -p no:django

# Run a single test
pytest phoxtail/cli/tests/test_config.py::TestClassName::test_name -p no:django

# Run tests matching a name pattern
pytest phoxtail/cli/tests/ -k "test_booking" -v -p no:django

# Stop on first failure
pytest phoxtail/cli/tests/ -x -p no:django
```

> **Why `-p no:django`?** The `pytest-django` plugin is installed (pulled in by
> engine dependencies) and tries to bootstrap Django at startup, which fails
> outside a Django project context. Disabling the plugin lets the CLI tests run
> without a Django settings module.

### Engine tests

Engine tests require Django and the `[engine]` optional dependency:

```bash
# Run the engine test suite
DJANGO_SETTINGS_MODULE=phoxtail.core.tests.settings pytest phoxtail/core/tests/

# Run a specific engine test file
DJANGO_SETTINGS_MODULE=phoxtail.core.tests.settings pytest phoxtail/core/tests/permissions/test_policies.py
```

> Engine tests use their own minimal Django settings module at
> `phoxtail/core/tests/settings.py` and are completely separate from the CLI
> tests — each suite can run independently.

## Structure

Tests live in `phoxtail/cli/tests/`, co-located with the CLI subsystem:

```
phoxtail/cli/tests/
├── conftest.py              ← shared fixtures (project_dir, config cache clearing)
├── test_commands.py         ← CLI command registration and routing
├── test_config.py           ← phoxtail.toml loading and merging
├── test_db.py               ← hostname localization logic
├── test_hatch.py            ← project scaffolding wizard
├── test_media.py            ← media sync operations
├── test_templates.py        ← template rendering (docker, nginx, env)
├── test_utils_docker.py     ← docker command wrappers
├── test_utils_env.py        ← .env file reading
└── test_verify_email.py     ← verify_email management command
```

Each test file maps to a module or concern, not a command. This keeps tests focused on testable units rather than CLI entry points.

## What to test

**Template rendering** — pure input/output. Given a context dict, does the template produce correct content? Test every conditional branch (dev/prod, booking on/off, wildcard/standard).

**Utility functions** — `read_env_value`, `docker_manage`, `docker_db`. These are shared across commands and have clear contracts.

**Domain logic** — functions like `_localize_hostnames` and `_deep_localize` that transform data. Test edge cases: IP addresses, subdomains, JSON-in-strings, no-op scenarios.

**Docker utilities** — mock `subprocess.run` to verify command construction and error propagation. Never call real Docker in tests.

## What not to test

**Interactive prompts** — Typer/questionary prompts are UI, not logic. The logic they feed into (template rendering, file writing) is already tested.

**File I/O in commands** — commands call `output.write_text(content)`. Testing that `Path.write_text` works is testing the stdlib. Test the content instead.

## Conventions

- Group related tests in classes (`TestDeepLocalize`, `TestComposeTemplate`)
- Use `setup_method` for shared state within a class
- Use `conftest.py` fixtures for shared state across files
- Mock subprocess calls — never run real Docker or SSH in tests
- Test the contract (what goes in, what comes out), not the implementation
- Config cache (`load_config.cache_clear()`) must be cleared in tests when changing `phoxtail.toml` content — the `project_dir` fixture in `conftest.py` handles this automatically

## Engine app testing

Engine apps (`phoxtail.core`) have their own Django test environment:

- Engine tests require the `[engine]` optional dependency (`pip install -e ".[engine,dev]"`)
- A minimal Django settings module lives at `phoxtail/core/tests/settings.py` (test database, minimal `INSTALLED_APPS`)
- Engine tests are separate from CLI tests — CLI tests must continue to run without Django

## Project template testing

Management commands that live in `phoxtail/project_template/` (e.g. `verify_email`) are tested
with mocked Django/allauth dependencies — no running Django instance required. The test fixtures
stub `sys.modules` entries for Django and allauth so the command module can be imported and
exercised in isolation. See `test_verify_email.py` for the pattern.
