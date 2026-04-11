# App Migration Guide

How to migrate a Django app from the upstream project
(`phoxtail-project`) into the `phoxtail` library package as a reusable,
optional app.

This guide was written after migrating **blog**; the same process
applies to **booking** and any future app clusters.

---

## Prerequisites

- The app to migrate already works in `phoxtail-project`.
- Its models, templates, and template tags are self-contained (no
  circular imports back into the upstream project).
- Any stream blocks / variants the app owns live under its own
  `management/data/blocks/` directory (the `populate_streams` command
  auto-discovers these from every installed app).

## Step-by-step

### 1. Copy the app into the package

Create `phoxtail/<app_name>/` with the standard layout:

```
phoxtail/<app_name>/
├── __init__.py
├── apps.py            # PhoxtailAppConfig subclass, name="phoxtail.<app_name>"
├── models.py
├── streams.py         # StreamField block definitions (if any)
├── migrations/
├── templates/
├── templatetags/
└── management/
    └── data/
        └── blocks/    # block.yaml + schema.json + variants
```

Key conventions:

| Field | Convention | Example |
|-------|-----------|---------|
| `AppConfig.name` | `phoxtail.<app_name>` | `phoxtail.blog` |
| `AppConfig.label` | `phoxtail_<app_name>` | `phoxtail_blog` |
| Template tags module | Named to avoid collisions | `phoxtail_blog_tags` |

The `AppConfig` should subclass `phoxtail.core.app_config.PhoxtailAppConfig`
and declare any integration the app needs (URL mount, context processors,
middleware, default settings, celery requirement, pip requirements,
dependencies on other phoxtail apps). See
[PhoxtailAppConfig reference](../apps/phoxtail-app-config.md) for the
full field list.

```python
# phoxtail/<app_name>/apps.py
from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount

class PhoxtailMyAppConfig(PhoxtailAppConfig):
    name = "phoxtail.my_app"
    label = "phoxtail_my_app"
    url_mount = UrlMount(prefix="my-app/", module="phoxtail.my_app.urls")
    context_processors = ["phoxtail.my_app.context_processors.my_ctx"]
```

### 2. Move block data out of streams

If the app's blocks previously lived under
`phoxtail/streams/management/data/blocks/`, move them into the app's own
`management/data/blocks/` directory. The `populate_streams` command
discovers `management/data/` directories across **all** installed apps,
so no command changes are needed — just relocate the files.

### 3. Register the app as an optional dependency

In `pyproject.toml`:

```toml
[project.optional-dependencies]
# New extra that pulls in engine
<app_name> = [
    "phoxtail[engine]",
]

# Add to dev so CI installs it
dev = [
    ...
    "phoxtail[engine,<app_name>,docs]",
]
```

Also register package data so templates and data files are included in
the built wheel:

```toml
[tool.setuptools.package-data]
"phoxtail.<app_name>" = ["templates/**/*", "management/data/**/*"]
```

### 4. Make the app selectable during hatch

In `phoxtail/cli/hatch.py`, add an entry to `OPTIONAL_APPS`:

```python
OPTIONAL_APPS = [
    {"name": "Blog", "value": "phoxtail.blog"},
    {"name": "Booking", "value": "phoxtail.booking"},  # new
]
```

The hatch wizard presents a checkbox prompt **before** scaffolding.
Selected apps are written verbatim into the generated project's
`INSTALLED_APPS`. At Django startup, `wire_apps(globals())` in
`src/settings/<env>.py` walks those entries, finds each
`PhoxtailAppConfig`, expands `depends_on`, and merges the app's
URL mount, context processors, middleware, default settings, and
celery requirement into the settings module. **No hatch-time injection,
markers, or context-processor bookkeeping — declare it in `apps.py`
and the runtime does the rest.**

If your app needs extra pip requirements (e.g. `celery`), declare them
in `PhoxtailAppConfig.requirements`. Hatch collects requirements from
the selected apps and appends them to `requirements.in` after rendering.

### 5. Validate block app references

Blocks that reference app-specific models (e.g. `page_types` or schema
`target_model` fields) include the app label. The `populate_streams`
command validates these references at import time and **skips** blocks
whose referenced apps are not installed. This means:

- Blog blocks referencing `phoxtail_blog.BlogPage` will only be created
  when `phoxtail.blog` is in `INSTALLED_APPS`.
- No manual conditional logic is needed.

### 6. Update tests

- Mock `questionary.checkbox` (returns `[]`) in any hatch test that
  doesn't use `--no-wizard`.
- Add wiring tests for your app's `PhoxtailAppConfig` if it declares
  non-trivial integration (url mount, context processors, celery,
  etc.), using the same pattern as `phoxtail/core/tests/test_wiring.py`.

### 7. Verify

```bash
make lint-check
make test
```

Confirm:

- All existing tests pass.
- A hatched project with the new app selected starts up with the app's
  URLs mounted and context processors active.
- `populate_streams` discovers blocks from the new app's data directory.

## Checklist

Use this as a quick reference when migrating the next app:

- [ ] Create `phoxtail/<app>/` with a `PhoxtailAppConfig` subclass, models, templates
- [ ] Declare `url_mount`, `context_processors`, `middleware`,
      `default_settings`, `requires_celery`, `requirements`, and
      `depends_on` on the `PhoxtailAppConfig` as needed
- [ ] Move block data from `streams/management/data/` → `<app>/management/data/`
- [ ] Add optional dependency extra in `pyproject.toml`
- [ ] Add package-data entry in `pyproject.toml`
- [ ] Add entry to `OPTIONAL_APPS` in `hatch.py`
- [ ] Mock `questionary.checkbox` in hatch tests
- [ ] `make lint-check && make test` — all green
