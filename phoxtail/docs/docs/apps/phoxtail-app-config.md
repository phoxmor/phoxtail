# PhoxtailAppConfig

`PhoxtailAppConfig` is the base `AppConfig` every optional phoxtail app
subclasses to declare its integration with a Django project. It is the
public interface that lets optional apps ship as independent packages:
a project installs the app, drops its dotted name into
`INSTALLED_APPS`, and the runtime wiring merges everything the app
needs into settings and URLs without touching the project template,
the CLI, or any glue code.

The class lives in `phoxtail.core.app_config`. The runtime that reads
these declarations lives in `phoxtail.core.wiring` and is invoked by
each generated settings module via `wire_apps(globals())`.

## The base class

```python
from dataclasses import dataclass
from django.apps import AppConfig


@dataclass
class UrlMount:
    prefix: str
    module: str
    namespace: str | None = None


class PhoxtailAppConfig(AppConfig):
    depends_on: list[str] = []
    url_mount: UrlMount | None = None
    context_processors: list[str] = []
    middleware: list[str] = []
    default_settings: dict = {}
    requires_celery: bool = False
    requirements: list[str] = []
```

Every field is optional. A `PhoxtailAppConfig` that leaves them all
at their defaults is still valid — it just contributes nothing beyond
the normal Django `AppConfig` behavior.

## Field reference

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `depends_on` | `list[str]` | `[]` | Dotted names of other phoxtail apps this one requires. `wire_apps` expands these transitively into `INSTALLED_APPS` before wiring anything else. Cyclic dependencies raise `ValueError`. |
| `url_mount` | `UrlMount \| None` | `None` | Where the app's URL conf is mounted. `collect_url_patterns()` (called from `src/urls.py`) turns this into a `path(prefix, include(module))` — or `include((module, namespace))` when `namespace` is set. |
| `context_processors` | `list[str]` | `[]` | Dotted paths appended to `TEMPLATES[0]["OPTIONS"]["context_processors"]`. Deduplicated — adding the same processor twice is a no-op. |
| `middleware` | `list[str]` | `[]` | Dotted paths appended to the project's `MIDDLEWARE`. Deduplicated. |
| `default_settings` | `dict` | `{}` | Setting defaults applied via `settings_globals.setdefault(...)`. The project's existing settings always win — this is for "make it work out of the box" defaults, not for overriding user config. |
| `requires_celery` | `bool` | `False` | If any wired-in app sets this, `wire_apps` sets `PHOXTAIL_CELERY_ENABLED = True` in the settings module. Generated settings modules gate their Celery config block on this flag. Also drives hatch-time copying of `src/celery.py`. |
| `requirements` | `list[str]` | `[]` | Extra pip requirements appended to the hatched project's `requirements.in` when this app is selected in the hatch wizard. Has no runtime effect — it is a hatch-time hint only. |

## Precedence rules

- **INSTALLED_APPS order** — dependencies declared via `depends_on`
  are inserted at the first position where they are needed while
  preserving the user's original ordering for entries that are already
  present. Apps never appear twice.
- **context_processors / middleware** — appended in the order
  `wire_apps` visits `INSTALLED_APPS` (which is the dependency-resolved
  order). Duplicates are skipped, so the first occurrence wins.
- **default_settings** — applied via `setdefault`. If the project's
  `base.py` (or an earlier-wired app) already defined the key, the
  app's default is ignored. Between two apps that both set the same
  key, the app wired first wins.
- **requires_celery** — any single `True` wins. Turning it off
  requires removing the app that needs it.

## Minimal example — an app with only URLs

```python
# phoxtail/my_app/apps.py
from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount


class PhoxtailMyAppConfig(PhoxtailAppConfig):
    name = "phoxtail.my_app"
    label = "phoxtail_my_app"
    url_mount = UrlMount(
        prefix="my-app/",
        module="phoxtail.my_app.urls",
    )
```

Add `"phoxtail.my_app"` to a project's `INSTALLED_APPS` and its URL
conf is mounted at `/my-app/`. No changes to `src/urls.py`, no hatch
edits, no marker injection.

## Example — an app with a context processor

```python
class PhoxtailDashboardConfig(PhoxtailAppConfig):
    name = "phoxtail.dashboard"
    label = "phoxtail_dashboard"
    url_mount = UrlMount(
        prefix="dashboard/",
        module="phoxtail.dashboard.urls",
    )
    context_processors = [
        "phoxtail.dashboard.context_processors.dashboard_nav",
    ]
```

The processor is appended to the project's `TEMPLATES` at settings
load time. Templates that use `{{ dashboard_nav_items }}` work out of
the box.

## Example — an umbrella app with dependencies and celery

```python
class PhoxtailBookingConfig(PhoxtailAppConfig):
    name = "phoxtail.booking"
    label = "phoxtail_booking"
    depends_on = [
        "phoxtail.dashboard",
        "phoxtail.booking.core",
        "phoxtail.booking.services",
        "phoxtail.booking.events",
        "phoxtail.booking.subscriptions",
        "phoxtail.booking.reservations",
        "django_celery_beat",
    ]
    requires_celery = True
    requirements = ["celery", "django-celery-beat"]
    default_settings = {
        "CELERY_BROKER_URL": "redis://redis:6379/0",
        "CELERY_RESULT_BACKEND": "redis://redis:6379/0",
        "CELERY_ACCEPT_CONTENT": ["json"],
        "CELERY_TASK_SERIALIZER": "json",
        "CELERY_RESULT_SERIALIZER": "json",
        "CELERY_BEAT_SCHEDULER": (
            "django_celery_beat.schedulers:DatabaseScheduler"
        ),
    }
```

Selecting "Booking" in the hatch wizard writes the single dotted name
`"phoxtail.booking"` into the generated `INSTALLED_APPS`. At runtime,
`wire_apps` expands the umbrella: the dashboard, the five booking
subapps, and `django_celery_beat` join `INSTALLED_APPS`; the celery
default settings are merged (but not overridden if the project has
already configured them); and `PHOXTAIL_CELERY_ENABLED` is set so the
project's settings modules can activate their Celery config block.

Hatch also sees `requirements = ["celery", "django-celery-beat"]` and
appends those to `requirements.in`, and copies `src/celery.py` into
the project because `requires_celery` is True.

## How wiring runs

Each environment settings module in the project template ends with:

```python
from phoxtail.core.wiring import wire_apps
wire_apps(globals())
if PHOXTAIL_CELERY_ENABLED:
    CELERY_TIMEZONE = TIME_ZONE
```

`wire_apps` does the following, in order:

1. Expand `INSTALLED_APPS` via `depends_on` with cycle detection.
2. Walk the expanded list, importing each app's `.apps` module and
   looking for a `PhoxtailAppConfig` subclass (plain `AppConfig`
   subclasses are skipped).
3. Collect `context_processors`, `middleware`, `default_settings`,
   and the combined `requires_celery` flag.
4. Append context processors and middleware to the settings
   module's `TEMPLATES` and `MIDDLEWARE` (deduplicated).
5. Apply `default_settings` via `setdefault`.
6. Set `PHOXTAIL_CELERY_ENABLED`.

URL mounts are collected separately. The project template's
`src/urls.py` calls `collect_url_patterns()` from
`phoxtail.core.wiring`, which runs after Django's app registry is
ready, iterates `apps.get_app_configs()`, and returns a list of
`path()` entries that the project appends to its `urlpatterns`.

## Design constraints worth remembering

- **Settings load time, not `ready()`** — `wire_apps` runs while
  Django is still loading settings, before the app registry exists.
  It uses `importlib` directly. Do not put code that depends on the
  app registry inside `PhoxtailAppConfig` class-body declarations.
- **Class attributes, not instance attributes** — the wiring layer
  reads fields off the class, not off an instance. Don't set
  `default_settings` inside `ready()` or `__init__`.
- **One `PhoxtailAppConfig` per `apps.py`** — `find_phoxtail_config`
  returns the first subclass defined in the module.
- **No dependence on `INSTALLED_APPS` ordering for correctness** —
  if your app only works when another app appears before it in
  `INSTALLED_APPS`, declare that via `depends_on` instead of relying
  on the project template.
- **Plain AppConfigs still work** — apps that don't need any of this
  can keep subclassing `django.apps.AppConfig`. They are skipped by
  `wire_apps` entirely.

## Testing a new PhoxtailAppConfig

Wiring behavior is tested in `phoxtail/core/tests/test_wiring.py`
against a set of fake app configs in
`phoxtail/core/tests/wiring_testapps/`. When adding a new field or a
non-trivial app declaration, mirror that pattern: add a fake config
that exercises the new behavior, and assert that `wire_apps` produces
the expected settings dict.
