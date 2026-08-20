# Linting & Formatting
lint:
	-uv run ruff check --fix phoxtail/
	uv run ruff format phoxtail/

lint-check:
	uv run ruff check phoxtail/
	uv run ruff format --check phoxtail/

# The package ships py.typed, so its annotations are a contract with users.
# Any error fails the run; the configuration lives in pyproject.toml so the
# Makefile, an editor and CI all read the same rules.
typecheck:
	uv run mypy phoxtail/ $(ARGS)

# Packaging
# Setuptools caches a file list in the egg-info directory, and a stale one
# serves the old list — which makes a correct packaging fix read as inert.
# Cleaning first costs nothing and removes the trap rather than documenting it.
build:
	rm -rf dist build phoxtail.egg-info
	uv build $(ARGS)

# Migrations
# The autodetector compares models to migration files, so a model edited
# without a matching migration reports here and nowhere else.
check-migrations:
	DJANGO_SETTINGS_MODULE=phoxtail.core.tests.settings \
	uv run python -m django makemigrations --check --dry-run $(ARGS)

# Testing
test-cli:
	uv run pytest phoxtail/cli/tests/ -p no:django $(ARGS)

test-engine:
	uv run pytest phoxtail/core/tests/ phoxtail/streams/tests/ phoxtail/dashboard/tests/ $(ARGS)

test-tokens:
	DJANGO_SETTINGS_MODULE=phoxtail.tokens.tests.settings uv run pytest phoxtail/tokens/tests/ $(ARGS)

test:
	uv run pytest $(ARGS)

test-cov:
	uv run pytest --cov --cov-report=term-missing $(ARGS)
