# Autonomous Apps Refactor — Implementation Guide

**Status:** Planned
**Scope:** Replace the current hatch-time feature injection (markers, dicts, env-var flags) with a runtime app self-wiring system. Make optional phoxtail apps truly autonomous so they can eventually ship as separate PyPI packages without any changes to the hatch CLI or project template.

This document is intended to be **sufficient to complete the refactor end-to-end without re-deriving context**. Read once, execute.

---

## 1. Why we're doing this

The current system distributes knowledge about each optional app across four locations:

1. **`phoxtail/cli/hatch.py`** — hardcoded dicts: `OPTIONAL_APPS`, `APP_GROUPS`, `APP_DEPENDENCIES`, `APP_CONTEXT_PROCESSORS`, `APP_URL_PATTERNS`.
2. **`phoxtail/project_template/src/settings/base.py`** — marker comments (`# {{ phoxtail_optional_apps }}`, `# {{ phoxtail_context_processors }}`), feature-flag env reads (`FEATURE_ACTIVATE_DASHBOARD`), static celery config, hardcoded `django_celery_beat` in `INSTALLED_APPS`.
3. **`phoxtail/project_template/src/urls.py`** — marker comment (`# {{ phoxtail_optional_urls }}`).
4. **`phoxtail/cli/templates/env/*.env`** — `FEATURE_ACTIVATE_*=...` lines.

Adding a new optional app means touching every one of these. This already scales badly at three optional apps (Blog, Dashboard, Booking). The moment we split these into separate PyPI packages — the long-term plan in `internal/package-vision.md` — the CLI can't know about them anyway, so this architecture collapses.

**Additional irritants this refactor kills:**

- **`src/celery.py` is always shipped** even when the hatched project has no celery consumer. The only consumer in the entire codebase is `phoxtail.booking.events`. Every non-booking project carries dead code.
- **`src/__init__.py` wraps the celery import in `try/except ImportError`** — a hack to paper over celery being optional-but-always-shipped.
- **`{% is_feature_enabled 'activate_dashboard' %}`** — a template tag that reads `settings.FEATURE_ACTIVATE_DASHBOARD` to answer a question Django already answers via `django.apps.apps.is_installed("phoxtail.dashboard")`. It conflates "is this app installed?" with "is this policy on?" (the latter being `FEATURE_ALLOW_SIGNUP`, which is a real runtime toggle, not an app-presence check).
- **Testing pattern** in `docs/patterns/testing.md` requires setting `os.environ["FEATURE_ACTIVATE_BOOKING"] = "True"` **before** importing settings, relying on the subtle `setdefault` semantics of `environ.Env.read_env`. Brittle and hard to explain.

---

## 2. The target architecture

### Principle

> Each optional app declares, in its own `apps.py`, everything the project needs to know to integrate it. The project template self-wires at settings load time by iterating `INSTALLED_APPS` and pulling each app's declarations.

**Hatch's job shrinks to**: show a checkbox of available apps and write their dotted names into `INSTALLED_APPS`. Nothing else.

**When booking becomes `pip install phoxtail-booking` in the future**: nothing in the hatch CLI or the project template changes. The user pip-installs it, adds `"phoxtail_booking"` to `INSTALLED_APPS`, and the runtime wiring picks up its declarations the same way.

### The abstraction

A new base class in `phoxtail/core/app_config.py`:

```python
from dataclasses import dataclass, field
from django.apps import AppConfig


@dataclass
class UrlMount:
    prefix: str               # e.g. "dashboard/"
    module: str               # e.g. "phoxtail.dashboard.urls"
    namespace: str | None = None


class PhoxtailAppConfig(AppConfig):
    """Base AppConfig for phoxtail apps that participate in autonomous wiring.

    Subclasses declare their integration requirements as class attributes.
    The project template's settings/base.py and urls.py read these at load
    time and auto-wire them. All fields are optional — an app that sets
    none of them is still a valid PhoxtailAppConfig.
    """

    # Apps that must be present for this app to function. Resolved
    # transitively and auto-appended to INSTALLED_APPS.
    depends_on: list[str] = []

    # URL include to mount. None means the app has no URLs.
    url_mount: UrlMount | None = None

    # Context processors to append to the default template engine.
    context_processors: list[str] = []

    # Middleware to append to MIDDLEWARE. Order-sensitive: use
    # middleware_before/middleware_after for strict ordering if needed.
    middleware: list[str] = []

    # Settings the app wants to contribute. Applied via setdefault —
    # user settings always win.
    default_settings: dict = {}

    # If any installed config has this True, celery bootstrap is enabled.
    requires_celery: bool = False

    # Requirements to add to requirements.in when this app is selected
    # at hatch time. Only used by hatch; ignored at runtime.
    requirements: list[str] = []
```

**Why class attributes, not `@property` / `ready()` hooks**: we need these values *before* the Django app registry is ready — at settings load time. Class attributes are readable via `importlib.import_module(f"{app}.apps")` without instantiating anything.

---

## 3. The wiring helper

**New file:** `phoxtail/core/wiring.py`

```python
"""Runtime wiring for PhoxtailAppConfig-based apps.

Called from src/settings/base.py once INSTALLED_APPS is assembled. Walks
INSTALLED_APPS, imports each app's `.apps` module, finds the
PhoxtailAppConfig subclass, and merges its declarations into the
caller's settings namespace.

Must run at settings load time — Django's app registry is NOT yet
populated at this point, so we use importlib directly.
"""

import importlib
import inspect

from phoxtail.core.app_config import PhoxtailAppConfig


def _find_phoxtail_config(dotted_app: str) -> type[PhoxtailAppConfig] | None:
    """Import `{dotted_app}.apps` and return its PhoxtailAppConfig subclass.

    Returns None if the app has no apps.py, or no PhoxtailAppConfig
    subclass (i.e. it uses plain django.apps.AppConfig).
    """
    try:
        module = importlib.import_module(f"{dotted_app}.apps")
    except ImportError:
        return None

    for _, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, PhoxtailAppConfig)
            and obj is not PhoxtailAppConfig
            and obj.__module__ == module.__name__
        ):
            return obj
    return None


def _resolve_dependencies(installed_apps: list[str]) -> list[str]:
    """Expand INSTALLED_APPS to include transitive `depends_on` values.

    Preserves original order; appends missing dependencies at the first
    position they're needed. Raises ValueError on cycles.
    """
    result: list[str] = []
    seen: set[str] = set()
    chain: set[str] = set()

    def visit(app: str) -> None:
        if app in seen:
            return
        if app in chain:
            raise ValueError(f"Circular dependency in phoxtail apps: {app}")
        chain.add(app)
        config = _find_phoxtail_config(app)
        if config is not None:
            for dep in config.depends_on:
                visit(dep)
        chain.discard(app)
        seen.add(app)
        result.append(app)

    for app in installed_apps:
        visit(app)
    return result


def wire_apps(settings_globals: dict) -> None:
    """Mutate a settings module's globals() to auto-wire PhoxtailAppConfigs.

    Idempotent: safe to call more than once (though you shouldn't).
    Call from settings/base.py AFTER INSTALLED_APPS, TEMPLATES, and
    MIDDLEWARE are defined, and BEFORE any code that reads those values.
    """
    installed = settings_globals["INSTALLED_APPS"]
    settings_globals["INSTALLED_APPS"] = _resolve_dependencies(installed)

    # Collect declarations from every PhoxtailAppConfig in INSTALLED_APPS.
    extra_context_processors: list[str] = []
    extra_middleware: list[str] = []
    default_settings: dict = {}
    celery_enabled = False

    for app in settings_globals["INSTALLED_APPS"]:
        config = _find_phoxtail_config(app)
        if config is None:
            continue
        extra_context_processors.extend(config.context_processors)
        extra_middleware.extend(config.middleware)
        for key, value in config.default_settings.items():
            default_settings.setdefault(key, value)
        if config.requires_celery:
            celery_enabled = True

    # Merge context processors into the first template engine.
    if extra_context_processors and settings_globals.get("TEMPLATES"):
        cps = settings_globals["TEMPLATES"][0]["OPTIONS"].setdefault(
            "context_processors", []
        )
        for cp in extra_context_processors:
            if cp not in cps:
                cps.append(cp)

    # Append middleware.
    middleware = settings_globals.setdefault("MIDDLEWARE", [])
    for mw in extra_middleware:
        if mw not in middleware:
            middleware.append(mw)

    # setdefault-merge app-provided default settings. User settings win.
    for key, value in default_settings.items():
        settings_globals.setdefault(key, value)

    settings_globals.setdefault("PHOXTAIL_CELERY_ENABLED", celery_enabled)


def collect_url_patterns():
    """Return a list of url path() entries from every PhoxtailAppConfig.

    Call from src/urls.py after the Django app registry is ready (i.e.
    at module load of urls.py, which happens after apps are loaded).
    At that point we CAN use django.apps.apps.get_app_configs().
    """
    from django.apps import apps
    from django.urls import include, path

    patterns = []
    for config in apps.get_app_configs():
        if not isinstance(config, PhoxtailAppConfig):
            continue
        mount = config.url_mount
        if mount is None:
            continue
        if mount.namespace:
            patterns.append(
                path(mount.prefix, include((mount.module, mount.namespace)))
            )
        else:
            patterns.append(path(mount.prefix, include(mount.module)))
    return patterns
```

### Precedence rules

1. **`INSTALLED_APPS` order**: user-written order preserved; dependencies inserted in place via topological visit. If booking already depends on dashboard and the user lists booking first, dashboard is inserted before booking in the final list.
2. **Context processors**: appended to the default engine (`TEMPLATES[0]`), deduplicated. Django's core processors stay first (important for `request`/`auth`/`messages`).
3. **Middleware**: appended. Apps that need to run *early* must document that they do, and the integrator can hand-place the middleware ahead of `wire_apps()`. We don't support `middleware_before` in v1 — YAGNI; revisit if we ever have an app that needs it.
4. **Default settings**: `setdefault` semantics. User-authored settings (anything set before `wire_apps()` is called) always win. Multiple apps setting the same key → first one wins. Apps should document their defaults.
5. **`PHOXTAIL_CELERY_ENABLED`**: OR across all configs. Also `setdefault` so a user can force it to `True` or `False`.

---

## 4. Migration map — what each current construct becomes

| Current construct | New location | Notes |
|---|---|---|
| `OPTIONAL_APPS` list in `hatch.py` | Stays — needed for the checkbox UI | Eventually auto-discovered by scanning `phoxtail.*`; not in v1 |
| `APP_GROUPS["phoxtail.booking"]` | Umbrella `phoxtail.booking` AppConfig with `depends_on = ["phoxtail.booking.core", ...]` | New file: `phoxtail/booking/apps.py` |
| `APP_DEPENDENCIES["phoxtail.booking"] = ["phoxtail.dashboard"]` | `PhoxtailBookingConfig.depends_on` | In the umbrella config |
| `APP_CONTEXT_PROCESSORS["phoxtail.dashboard"]` | `PhoxtailDashboardConfig.context_processors` | Moved into `phoxtail/dashboard/apps.py` |
| `APP_URL_PATTERNS["phoxtail.dashboard"]` | `PhoxtailDashboardConfig.url_mount = UrlMount("dashboard/", "phoxtail.dashboard.urls")` | Moved into `phoxtail/dashboard/apps.py` |
| `APPS_MARKER` in `base.py` | Stays — this is the one legitimate injection point | Only inserts the user's chosen apps verbatim |
| `CTX_MARKER` in `base.py` | **Deleted** — replaced by `wire_apps(globals())` | |
| `URLS_MARKER` in `urls.py` | **Deleted** — replaced by `urlpatterns += collect_url_patterns()` | |
| `FEATURE_ACTIVATE_DASHBOARD = env.bool(...)` | **Deleted** | App presence is the source of truth |
| `FEATURE_ACTIVATE_BOOKING` (in docs) | **Deleted** | Same |
| `FEATURE_ALLOW_SIGNUP` | **Renamed** → `PHOXTAIL_ALLOW_SIGNUP` | It's a real policy, not an app-presence flag. Survives but under a name that makes its nature clear |
| `{% is_feature_enabled 'activate_dashboard' %}` | `{% app_installed 'phoxtail.dashboard' as is_dashboard_enabled %}` | New tag; see §6 |
| `{% is_feature_enabled 'allow_signup' %}` (if it existed) | `{% setting_enabled 'PHOXTAIL_ALLOW_SIGNUP' %}` | Single-purpose policy tag |
| `is_feature_enabled` tag | **Deleted** | Replaced by the two tags above |
| Static `"django_celery_beat"` in `INSTALLED_APPS` | Added via `PhoxtailBookingConfig.depends_on` (or a separate declaration) | Only present when booking is installed |
| Static `CELERY_*` settings in `base.py` | Moved into `PhoxtailBookingConfig.default_settings` | Only applied when booking is installed |
| `src/celery.py` | Conditionally copied by `_copy_template` | Only when a selected app has `requires_celery = True` |
| `src/__init__.py` `try/except ImportError` | **Deleted** | Gated on `settings.PHOXTAIL_CELERY_ENABLED` instead |
| `celery`, `django-celery-beat` in template `requirements.in` | Conditionally written by hatch | Via the new `requirements` attribute on `PhoxtailAppConfig`, OR a simple hardcoded "if celery enabled" check in hatch — see §8 |
| Testing pattern: `os.environ["FEATURE_ACTIVATE_BOOKING"] = "True"` | Add `"phoxtail.booking"` directly to `INSTALLED_APPS` in `test.py` | Simpler, no env-var juggling |

---

## 5. Phased execution plan

Each phase is independently verifiable. **Do them in order.** Run `make test-cli` after each phase; run `make test-engine` after Phase 2–4 (they touch the engine apps).

### Phase 0 — Prep

- Read this document end-to-end.
- Create a working branch.
- Skim `phoxtail/dashboard/apps.py`, `phoxtail/booking/core/apps.py`, and `phoxtail/project_template/src/settings/base.py` so the current state is fresh.

### Phase 1 — Introduce `PhoxtailAppConfig` and `wiring.py`

**No template changes yet.** This phase ships the machinery but doesn't use it.

1. Create `phoxtail/core/app_config.py` with `PhoxtailAppConfig` and `UrlMount` as specified in §2.
2. Create `phoxtail/core/wiring.py` with `_find_phoxtail_config`, `_resolve_dependencies`, `wire_apps`, `collect_url_patterns` as specified in §3.
3. Export them from `phoxtail.core` if that module has an `__init__.py` barrel (check first; don't add one if the package doesn't already export).
4. Add tests: `phoxtail/core/tests/test_wiring.py`
   - Two fake app configs in `phoxtail/core/tests/testapp_a/apps.py` and `testapp_b/apps.py`.
   - Test: `_resolve_dependencies` handles linear deps.
   - Test: `_resolve_dependencies` detects cycles.
   - Test: `wire_apps` merges context processors without duplicating.
   - Test: `wire_apps` appends middleware without duplicating.
   - Test: `wire_apps` uses `setdefault` for `default_settings` (user settings win).
   - Test: `wire_apps` sets `PHOXTAIL_CELERY_ENABLED` correctly.
   - Test: apps that use plain `AppConfig` (not `PhoxtailAppConfig`) are skipped silently.
5. Verify: `make test-engine` passes.

**Success criteria**: new files land, new tests pass, no existing code uses them yet.

### Phase 2 — Migrate `phoxtail.dashboard` to declare itself

1. Edit `phoxtail/dashboard/apps.py`:
   ```python
   from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount

   class PhoxtailDashboardConfig(PhoxtailAppConfig):
       default_auto_field = "django.db.models.BigAutoField"
       name = "phoxtail.dashboard"
       label = "phoxtail_dashboard"
       verbose_name = "Phoxtail Dashboard"

       url_mount = UrlMount(prefix="dashboard/", module="phoxtail.dashboard.urls")
       context_processors = [
           "phoxtail.dashboard.context_processors.dashboard_nav",
       ]

       def ready(self):
           from django.utils.module_loading import autodiscover_modules
           autodiscover_modules("dashboard")
   ```
2. **Don't** remove the `hatch.py` dicts yet. Dashboard is still wired the old way; the declaration is dormant until the template starts calling `wire_apps`.
3. Run `make test-engine` — nothing should break.

### Phase 3 — Create the booking umbrella and migrate `phoxtail.booking`

1. Create `phoxtail/booking/apps.py`:
   ```python
   from phoxtail.core.app_config import PhoxtailAppConfig

   class PhoxtailBookingConfig(PhoxtailAppConfig):
       name = "phoxtail.booking"
       label = "phoxtail_booking"
       verbose_name = "Phoxtail Booking"

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
       default_settings = {
           "CELERY_BROKER_URL": "redis://redis:6379/0",
           "CELERY_RESULT_BACKEND": "redis://redis:6379/0",
           "CELERY_ACCEPT_CONTENT": ["json"],
           "CELERY_TASK_SERIALIZER": "json",
           "CELERY_RESULT_SERIALIZER": "json",
           "CELERY_TASK_TRACK_STARTED": True,
           "CELERY_TASK_TIME_LIMIT": 30 * 60,
       }
       requirements = ["celery", "django-celery-beat"]
   ```
   **Note**: `phoxtail.booking` as an umbrella needs `phoxtail/booking/__init__.py` to exist (it does — empty file). Django will find the AppConfig via the dotted name lookup. The umbrella doesn't ship migrations or models; it's purely a coordinator. Verify Django is happy registering a package-only AppConfig by running `make test-booking` after this step.
2. `phoxtail/booking/core/apps.py` stays a plain `AppConfig` — all the coordination lives in the umbrella.
3. **Important**: `depends_on` is transitive and order-preserving. Listing dashboard first means it gets inserted into `INSTALLED_APPS` before any booking subapp. Same for `django_celery_beat`.
4. `CELERY_TIMEZONE` is intentionally omitted from `default_settings` — it depends on `TIME_ZONE` which is set in user settings. The base template will handle it explicitly: `if PHOXTAIL_CELERY_ENABLED: CELERY_TIMEZONE = TIME_ZONE`. Document this edge case inline.

### Phase 4 — Wire the project template to call `wire_apps`

This is the biggest diff. Do it carefully; test with `phoxtail hatch` end-to-end after.

1. **`phoxtail/project_template/src/settings/base.py`**:
   - Delete the `# {{ phoxtail_context_processors }}` marker line.
   - Delete `"django_celery_beat",` from `INSTALLED_APPS`.
   - Delete the whole `# Celery Configuration` block (lines 231–239 in current file).
   - Delete `FEATURE_ACTIVATE_DASHBOARD = env.bool(...)`.
   - Rename `FEATURE_ALLOW_SIGNUP` → `PHOXTAIL_ALLOW_SIGNUP`.
   - At the very end of the file, add:
     ```python
     # Autonomous app wiring. Must come AFTER INSTALLED_APPS, TEMPLATES,
     # MIDDLEWARE, and any user-defined settings. Reads PhoxtailAppConfig
     # declarations and merges them into this module's globals.
     from phoxtail.core.wiring import wire_apps

     wire_apps(globals())

     if PHOXTAIL_CELERY_ENABLED:
         CELERY_TIMEZONE = TIME_ZONE
     ```
2. **`phoxtail/project_template/src/urls.py`**:
   - Delete the `# {{ phoxtail_optional_urls }}` marker line.
   - After `urlpatterns = [...]`, add:
     ```python
     from phoxtail.core.wiring import collect_url_patterns
     urlpatterns += collect_url_patterns()
     ```
3. **`phoxtail/project_template/src/__init__.py`**:
   - Replace the `try/except ImportError` block with:
     ```python
     """Django project initialization."""
     from django.conf import settings

     if getattr(settings, "PHOXTAIL_CELERY_ENABLED", False):
         from .celery import app as celery_app
         __all__ = ("celery_app",)
     ```
     **Caveat**: importing `django.conf.settings` at `src/__init__.py` load time triggers settings resolution very early. Test carefully — if Django complains about app-not-ready, fall back to importing celery inside a lazy function or use `django.apps.apps.ready`.
     **Fallback form** if the above fails:
     ```python
     def _load_celery_app():
         from django.conf import settings
         if getattr(settings, "PHOXTAIL_CELERY_ENABLED", False):
             from .celery import app
             return app
         return None

     celery_app = _load_celery_app()
     __all__ = ("celery_app",) if celery_app else ()
     ```
4. **`phoxtail/cli/templates/env/development.env`** and **`production.env`**:
   - Rename `FEATURE_ALLOW_SIGNUP` → `PHOXTAIL_ALLOW_SIGNUP` (keep the `{{ allow_signup | lower }}` Jinja binding).
   - Remove any `FEATURE_ACTIVATE_*` lines (there shouldn't be any currently — verify).

### Phase 5 — Shrink `hatch.py`

Only once Phase 4 is green on a freshly-hatched project.

1. Delete from `phoxtail/cli/hatch.py`:
   - `APP_GROUPS` dict
   - `APP_DEPENDENCIES` dict
   - `APP_CONTEXT_PROCESSORS` dict
   - `APP_URL_PATTERNS` dict
   - `CTX_MARKER` constant
   - `URLS_MARKER` constant
   - All the dep/group/ctx/url logic inside `_copy_template`
2. Keep:
   - `OPTIONAL_APPS` list
   - `APPS_MARKER` and the code that writes selected apps into it
   - `PLACEHOLDER` and the project-name replacement
3. **New**: hatch needs to know whether any selected app requires celery, so it can decide whether to copy `src/celery.py` and whether to add celery to `requirements.in`. Two options:
   - **(a)** Import each selected app's `PhoxtailAppConfig` at hatch time and check `requires_celery` / `requirements`. Pro: single source of truth. Con: hatch starts importing Django app configs, which is fine as long as we don't touch Django itself (`PhoxtailAppConfig` subclasses `AppConfig`, which imports `django.apps` — acceptable since hatch already runs in the phoxtail venv).
   - **(b)** Hardcode a small `HATCH_APP_INFO` dict in hatch.py: `{"phoxtail.booking": {"celery": True, "extra_requirements": [...]}}`. Pro: zero import overhead. Con: duplicates knowledge.
   - **Choose (a)** — it aligns with the whole point of the refactor, and hatch already executes phoxtail CLI subprocesses.
4. `_copy_template` gains one new conditional: if no selected app has `requires_celery`, skip copying `src/celery.py` (add `src/celery.py` to a `CONDITIONAL_FILES` dict keyed by a predicate function).
5. For requirements: `_copy_template` appends each selected app's `requirements` list to the rendered `requirements.in` content before writing it. (The current `render_template("requirements/requirements.in", {})` call needs to grow a `extra_requirements` context var, or hatch concatenates after rendering.)

### Phase 6 — Replace `is_feature_enabled`

1. In `phoxtail/core/templatetags/phoxtail_core_tags.py`:
   - Delete `is_feature_enabled`.
   - Add:
     ```python
     @register.simple_tag
     def app_installed(dotted_name):
         """True if the given app is in INSTALLED_APPS."""
         from django.apps import apps
         return apps.is_installed(dotted_name)

     @register.simple_tag
     def setting_enabled(name):
         """True if the named setting is truthy."""
         return bool(getattr(settings, name, False))
     ```
2. Update every caller:
   - `phoxtail/dashboard/templates/phoxtail_dashboard/navigation/dock.html` — replace `{% is_feature_enabled 'activate_dashboard' as is_dashboard_enabled %}` with `{% app_installed 'phoxtail.dashboard' as is_dashboard_enabled %}`.
   - `phoxtail/dashboard/templates/phoxtail_dashboard/navigation/drawer.html` — same.
   - `phoxtail/dashboard/templates/phoxtail_dashboard/navigation/sidebar.html` — same.
   - `phoxtail/streams/management/data/blocks/navbar/variants/ground_state/default/template.html` — same (2 occurrences).
   - `phoxtail/streams/management/data/blocks/navbar/variants/ground_state/default_transparent/template.html` — same (2 occurrences).
3. Note: **the dashboard templates that check `activate_dashboard` are inside the dashboard app itself**. If the dashboard app is installed, the check is trivially true. Consider whether these checks are actually needed at all — they may be vestigial from before dashboard became optional. Decide case-by-case: inside dashboard's own templates, probably drop the check entirely. Inside `phoxtail.streams` navbar templates (which need to work whether dashboard is installed or not), keep the check.
4. `phoxtail/users/adapters.py` — replace `settings.FEATURE_ALLOW_SIGNUP` with `settings.PHOXTAIL_ALLOW_SIGNUP`.

### Phase 7 — Update tests

1. **`phoxtail/cli/tests/test_hatch.py`**:
   - Remove references to `APP_GROUPS`, `APP_DEPENDENCIES`, `CTX_MARKER`, `URLS_MARKER`.
   - Rewrite tests that asserted context-processor or URL injection: they should now assert that the generated project's `settings/base.py` contains `wire_apps(globals())` and `urls.py` contains `collect_url_patterns()`.
   - Add a test: hatching with booking selected produces an `INSTALLED_APPS` list that contains `"phoxtail.booking"` (not the expanded subapps — expansion happens at runtime now).
   - Add a test: hatching without booking does NOT copy `src/celery.py`.
   - Add a test: hatching with booking DOES copy `src/celery.py` and adds celery to `requirements.in`.
2. **`phoxtail/cli/tests/test_templates.py`**:
   - Update line 181 (`FEATURE_ALLOW_SIGNUP=true` → `PHOXTAIL_ALLOW_SIGNUP=true`).
   - Delete lines 182–183 (`FEATURE_ACTIVATE_DASHBOARD`, `FEATURE_ACTIVATE_BOOKING` assertions).
3. **`phoxtail/cli/tests/test_utils_env.py`** (lines 49–50): replace `FEATURE_ACTIVATE_BOOKING` with any surviving env key (e.g. `PHOXTAIL_ALLOW_SIGNUP`) — the test is about the env parser, not about that specific key.
4. **`phoxtail/core/tests/settings.py`**: already lists booking subapps directly. No `FEATURE_*` flag involved. Should keep working; verify with `make test-booking`.
5. **New tests for `wire_apps`** (from Phase 1, expand in Phase 7): add an end-to-end test that imports the generated project's `settings/base.py` in a subprocess and asserts `INSTALLED_APPS`, `TEMPLATES[0]["OPTIONS"]["context_processors"]`, and `PHOXTAIL_CELERY_ENABLED` reflect the selected apps correctly.

### Phase 8 — Update documentation

1. **`phoxtail/docs/docs/internal/package-vision.md`** — add a section noting that `PhoxtailAppConfig` is the public interface that makes the package split possible, and link to this guide.
2. **`phoxtail/docs/docs/internal/app-migration-guide.md`** — rewrite the sections that reference `APPS_MARKER`/`CTX_MARKER`/`URLS_MARKER` (lines 96, 139, etc.). The new guidance: "declare your app in `apps.py` by subclassing `PhoxtailAppConfig`; no hatch.py changes needed."
3. **`phoxtail/docs/docs/internal/dashboard-migration-plan.md`** — strike through references to the old marker system (lines 341–342).
4. **`phoxtail/docs/docs/internal/booking-migration-plan.md`** — same treatment (line 306).
5. **`phoxtail/docs/docs/apps/dashboard/registration.md`** — rewrite the section that shows `FEATURE_ACTIVATE_BOOKING = env.bool(...)` (lines 195–207). New pattern: "if booking is installed, its dashboard nav items are registered via its `ready()` hook. No env flag needed."
6. **`phoxtail/docs/docs/patterns/service-layer-users.md`** — line 137 references `FEATURE_ACTIVATE_BOOKING`. Rewrite to "the booking cluster may or may not be installed; check with `apps.is_installed('phoxtail.booking')`."
7. **`phoxtail/docs/docs/patterns/testing.md`** — rewrite the `os.environ["FEATURE_ACTIVATE_BOOKING"]` pattern (lines 65, 73, 302). New pattern: "add `'phoxtail.booking'` to `INSTALLED_APPS` in `src/settings/test.py`."
8. **`phoxtail/docs/docs/cli/configuration.md`** — replace `FEATURE_ALLOW_SIGNUP` with `PHOXTAIL_ALLOW_SIGNUP` (lines 27, 66).
9. **New doc: `phoxtail/docs/docs/apps/phoxtail-app-config.md`** — public reference for `PhoxtailAppConfig`: every field, precedence rules, minimal example, dependency examples. Wire it into `mkdocs.yml` under `Apps:`.

---

## 6. `is_feature_enabled` — the full replacement story

The current tag has two distinct jobs buried inside one API:

### Job A: "Is this optional app installed?"

**Current**: `{% is_feature_enabled 'activate_dashboard' %}` reading `settings.FEATURE_ACTIVATE_DASHBOARD`, set by an env var, parallel to `INSTALLED_APPS`.

**New**: `{% app_installed 'phoxtail.dashboard' %}` reading `django.apps.apps.is_installed(...)`. Single source of truth: `INSTALLED_APPS`. No env var. No parallel state.

**Locations affected** (verified via grep):
- `phoxtail/dashboard/templates/phoxtail_dashboard/navigation/dock.html` line 2
- `phoxtail/dashboard/templates/phoxtail_dashboard/navigation/drawer.html` line 66
- `phoxtail/dashboard/templates/phoxtail_dashboard/navigation/sidebar.html` line 26
- `phoxtail/streams/management/data/blocks/navbar/variants/ground_state/default/template.html` lines 151, 359
- `phoxtail/streams/management/data/blocks/navbar/variants/ground_state/default_transparent/template.html` lines 160, 372

**Inside-dashboard checks are vestigial**: dock/drawer/sidebar are shipped *by* the dashboard app. If they render, dashboard is installed. Drop the check entirely in those three files.

**Navbar streams templates** genuinely need the check — they live in `phoxtail.streams` and must work with or without dashboard. Keep the check, use `app_installed`.

### Job B: "Is this runtime policy on?"

**Current**: `settings.FEATURE_ALLOW_SIGNUP`, read directly in `phoxtail/users/adapters.py` (not via the template tag). There are no template usages of `is_feature_enabled` for `allow_signup` — the tag's docstring uses it as an example, but nothing actually calls it that way.

**New**: rename `FEATURE_ALLOW_SIGNUP` → `PHOXTAIL_ALLOW_SIGNUP` for consistency. Add a `setting_enabled` template tag for the general case (cheap to ship alongside `app_installed`; future-proof for any policy toggles that *do* need template access).

**Result**: `is_feature_enabled` is deleted. `app_installed` and `setting_enabled` replace it with explicit, single-purpose semantics.

---

## 7. Celery — the specific flow

| Step | Current | New |
|---|---|---|
| Install `celery` package | Always in `requirements.in` | Only when `requires_celery=True` app is selected |
| Install `django-celery-beat` | Always | Same |
| `INSTALLED_APPS += ["django_celery_beat"]` | Hardcoded | Added via `PhoxtailBookingConfig.depends_on` |
| `CELERY_*` settings | Hardcoded in `base.py` | In `PhoxtailBookingConfig.default_settings` (except `CELERY_TIMEZONE`) |
| Ship `src/celery.py` | Always | Only when any selected app has `requires_celery=True` |
| `src/__init__.py` imports celery app | Wrapped in `try/except ImportError` | Gated on `settings.PHOXTAIL_CELERY_ENABLED` |

**`CELERY_TIMEZONE` note**: this setting needs the value of `TIME_ZONE`, which lives in user settings. `wire_apps` runs before that assignment is visible in the `default_settings` dict (dict values are frozen at class-definition time). Solution: `base.py` explicitly handles it after calling `wire_apps`:

```python
wire_apps(globals())

if PHOXTAIL_CELERY_ENABLED:
    CELERY_TIMEZONE = TIME_ZONE
```

Same pattern applies to any setting that depends on another setting's value. Document this in the `PhoxtailAppConfig` reference doc.

---

## 8. Hatch reading `PhoxtailAppConfig` at CLI time

Hatch needs two pieces of info per selected app to decide what to copy:

1. Does it require celery? → determines whether to copy `src/celery.py`.
2. What extra requirements does it need? → appended to `requirements.in`.

Both live on `PhoxtailAppConfig`. Hatch can import them directly:

```python
# In hatch.py:
def _get_app_info(dotted_app: str) -> dict:
    """Import an optional app's PhoxtailAppConfig and return celery + requirements."""
    import importlib, inspect
    from phoxtail.core.app_config import PhoxtailAppConfig

    try:
        module = importlib.import_module(f"{dotted_app}.apps")
    except ImportError:
        return {"requires_celery": False, "requirements": []}

    for _, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, PhoxtailAppConfig)
            and obj is not PhoxtailAppConfig
            and obj.__module__ == module.__name__
        ):
            return {
                "requires_celery": obj.requires_celery,
                "requirements": obj.requirements,
            }
    return {"requires_celery": False, "requirements": []}
```

Note: this reuses the logic in `wiring._find_phoxtail_config`. **Extract into a shared helper** during Phase 1 (keep it in `phoxtail/core/wiring.py` or lift to `phoxtail/core/app_config.py`). Don't duplicate.

**Caveat on importing Django app configs from hatch**: `PhoxtailAppConfig` subclasses `django.apps.AppConfig`, which imports `django.apps`. This imports `django` but does not populate the app registry — it's safe at CLI time. The phoxtail venv already has Django installed. No subprocess needed.

---

## 9. Pitfalls and mitigations

### 9.1 Settings load order

`wire_apps` mutates `INSTALLED_APPS`, `TEMPLATES`, `MIDDLEWARE`, and arbitrary top-level settings keys. **It must run at a specific point** in `base.py`:

- **After** `INSTALLED_APPS`, `TEMPLATES`, `MIDDLEWARE`, and any user-authored settings they need to override.
- **Before** any code that reads those values for further processing (e.g. conditional feature branches).
- **At module scope**, not inside a function — Django imports settings once and caches.

**Mitigation**: put `wire_apps(globals())` as close to the end of `base.py` as possible — right before any `if PHOXTAIL_CELERY_ENABLED: ...` blocks. Document this clearly in a comment in the template.

### 9.2 `default_settings` dict mutation

`PhoxtailAppConfig.default_settings = {...}` is a *class attribute*. If `wire_apps` ever mutates it (it doesn't today, but future code might), the mutation leaks across configs. **Always copy on read**:

```python
for key, value in dict(config.default_settings).items():
    ...
```

The current `wire_apps` only reads, so this is a latent risk, not a current bug. Mention in the reference doc.

### 9.3 Environ/read_env ordering

`base.py` currently calls `environ.Env.read_env(os.path.join(BASE_DIR, ".env"))` very early. The old testing pattern (setting `FEATURE_ACTIVATE_BOOKING=True` in `os.environ` before import) relies on `read_env` using `setdefault` semantics. **After this refactor, that whole pattern goes away**. Test settings files should edit `INSTALLED_APPS` directly. Update `docs/patterns/testing.md` to reflect this.

### 9.4 Circular imports at settings load time

`wire_apps` imports `{app}.apps` for every app in `INSTALLED_APPS`. If any `apps.py` at the top level imports models, forms, signals, or other Django machinery that depends on the app registry being populated, **it will fail at settings load** — settings run before app registry is ready.

**Mitigation**: document in the `PhoxtailAppConfig` reference: "imports at the top of your `apps.py` must be lazy. Put model/form imports inside `ready()` or inside methods." This is already a well-known Django rule; we're just enforcing it more strictly.

**Verification**: Phase 2/3 must run `make test-engine` after each migration to catch any accidental eager imports in the migrated apps.

### 9.5 Running `wire_apps` inside `test.py`

`test.py` does `from .base import *` which triggers `wire_apps(globals())` in the `base` module. But `test.py` may subsequently modify `INSTALLED_APPS` (to add test-only apps). After modification, the wiring is stale: new apps won't have their declarations merged.

**Options**:
- **(a)** Don't run `wire_apps` in `base.py`; instead, run it in each concrete settings module (`development.py`, `production.py`, `test.py`) after they've finished customizing.
- **(b)** Document that modifying `INSTALLED_APPS` in derived settings requires re-calling `wire_apps(globals())`.

**Choose (a)**: move `wire_apps(globals())` out of `base.py` and into each concrete module. `base.py` becomes pure declarations; wiring happens at the leaf. This is cleaner and avoids the stale-wiring trap.

**Template changes**:
- `base.py`: do NOT call `wire_apps`. Add a comment explaining why.
- `development.py`: end with `from phoxtail.core.wiring import wire_apps; wire_apps(globals())`.
- `production.py`: same.
- `test.py`: same, at the very end after any `INSTALLED_APPS += [...]` additions.

Update Phase 4 step 1 accordingly: `wire_apps` goes in the three concrete modules, not `base.py`.

### 9.6 `phoxtail.booking` umbrella AppConfig without models

Django normally expects an AppConfig's `name` to correspond to a package that contains either models or other apps. `phoxtail.booking` contains subpackages but no `models.py`. **Verify** Django accepts this by running `python manage.py check` on a hatched project with booking enabled. If it complains, the workaround is to add an empty `phoxtail/booking/models.py` file. Cheap insurance.

### 9.7 `src/__init__.py` importing `django.conf.settings` at module load

Python imports `src.__init__` the first time any submodule is accessed. If celery is configured, `src/celery.py` imports `django.conf.settings`, which resolves `DJANGO_SETTINGS_MODULE` → imports `src.settings.development` → which imports `src` → which runs `src/__init__.py` → circular.

**Current code** avoids this by using `try/except ImportError`. We can't keep that hack.

**Mitigation**: the gating import in `src/__init__.py` must be **lazy**. Use the fallback form:

```python
def _load_celery_app():
    from django.conf import settings
    if getattr(settings, "PHOXTAIL_CELERY_ENABLED", False):
        from .celery import app
        return app
    return None

celery_app = _load_celery_app()
__all__ = ("celery_app",) if celery_app else ()
```

Actually — `_load_celery_app` runs at module import time, so it's not really lazy. The real fix: **don't import celery from `__init__.py` at all**. Celery 5+ doesn't require `from project import celery_app`; it only requires that `src/celery.py` exists and calls `app.autodiscover_tasks()`. The worker starts with `celery -A src worker` and imports `src.celery` directly.

**Decision**: delete the `celery_app` re-export from `src/__init__.py` entirely. Celery workers import `src.celery` directly. Update any docs/commands that reference `src.celery_app`.

**Verification**: check `Dockerfile` / `docker-compose.yaml` templates for references to how celery workers are started.

---

## 10. File-by-file change list (reference)

### New files

- `phoxtail/core/app_config.py` — `PhoxtailAppConfig`, `UrlMount`
- `phoxtail/core/wiring.py` — `wire_apps`, `collect_url_patterns`, `_find_phoxtail_config`, `_resolve_dependencies`
- `phoxtail/core/tests/test_wiring.py`
- `phoxtail/booking/apps.py` — umbrella `PhoxtailBookingConfig`
- `phoxtail/docs/docs/apps/phoxtail-app-config.md` — public reference

### Modified files

- `phoxtail/dashboard/apps.py` — subclass `PhoxtailAppConfig`, add `url_mount`, `context_processors`
- `phoxtail/project_template/src/settings/base.py` — delete `CTX_MARKER`, delete `django_celery_beat`, delete `CELERY_*`, delete `FEATURE_ACTIVATE_DASHBOARD`, rename `FEATURE_ALLOW_SIGNUP`
- `phoxtail/project_template/src/settings/development.py` — end with `wire_apps(globals())`
- `phoxtail/project_template/src/settings/production.py` — same
- `phoxtail/project_template/src/settings/test.py` — same
- `phoxtail/project_template/src/urls.py` — delete `URLS_MARKER`, add `collect_url_patterns()`
- `phoxtail/project_template/src/__init__.py` — delete celery re-export entirely
- `phoxtail/cli/hatch.py` — delete `APP_GROUPS`, `APP_DEPENDENCIES`, `APP_CONTEXT_PROCESSORS`, `APP_URL_PATTERNS`, `CTX_MARKER`, `URLS_MARKER`; add celery/requirements conditional via `_get_app_info`
- `phoxtail/cli/templates/env/development.env` — rename `FEATURE_ALLOW_SIGNUP` → `PHOXTAIL_ALLOW_SIGNUP`
- `phoxtail/cli/templates/env/production.env` — same
- `phoxtail/cli/templates/requirements/requirements.in` — remove `celery` and `django-celery-beat` (they become conditional)
- `phoxtail/core/templatetags/phoxtail_core_tags.py` — delete `is_feature_enabled`, add `app_installed`, add `setting_enabled`
- `phoxtail/users/adapters.py` — `settings.FEATURE_ALLOW_SIGNUP` → `settings.PHOXTAIL_ALLOW_SIGNUP`
- Navbar/dashboard templates listed in §6 — replace the template tag call
- `phoxtail/cli/tests/test_hatch.py` — update assertions (see Phase 7)
- `phoxtail/cli/tests/test_templates.py` — update assertions
- `phoxtail/cli/tests/test_utils_env.py` — update env-var used in test
- Docs listed in Phase 8

### Deleted files

- Possibly `src/celery.py` from the template if we move it to a conditional-copy pattern (it stays in the template dir but hatch skips it when not needed). **No file is deleted from the repo**; hatch just conditionally copies it.

---

## 11. Verification checklist (run after every phase)

- [ ] `make lint-check` passes (pre-existing errors in `phoxtail/core/models.py` are acceptable and unrelated)
- [ ] `make test-cli` passes
- [ ] `make test-engine` passes
- [ ] `make test-booking` passes (Phase 3 onward)
- [ ] Manual: hatch a project with no optional apps → starts cleanly, no celery files, no `FEATURE_*` in `.env`
- [ ] Manual: hatch a project with dashboard only → dashboard URLs mount, dashboard context processors active, still no celery
- [ ] Manual: hatch a project with booking → dashboard auto-included, celery files present, celery settings present, `INSTALLED_APPS` contains all booking subapps plus `django_celery_beat`
- [ ] Manual: hatch a project, run `python manage.py check` — no warnings
- [ ] Manual: hatch a project with booking, run a celery task — works

---

## 12. Out of scope (explicit non-goals)

- **Auto-discovering optional apps** by scanning `phoxtail.*` submodules. v1 keeps the explicit `OPTIONAL_APPS` list in `hatch.py`. Move to discovery later if it proves tedious.
- **Ordering hints for middleware** (`middleware_before` / `middleware_after`). v1 just appends. If an app ever needs strict middleware ordering, revisit.
- **Versioning of the `PhoxtailAppConfig` interface**. Once other packages depend on it, changes become breaking. Not a v1 concern, but note it in the reference doc.
- **Migrating `phoxtail.blog`** to `PhoxtailAppConfig`. Blog has no URL mount, no context processors, no celery, no middleware. It works fine as a plain AppConfig. Leave it alone until it grows a reason.

---

## 13. Commit strategy

One commit per phase. Phase numbers in commit messages for reviewability:

1. `feat(core): add PhoxtailAppConfig and wiring helpers`
2. `refactor(dashboard): declare url mount and context processors via PhoxtailAppConfig`
3. `refactor(booking): add umbrella PhoxtailBookingConfig with celery declarations`
4. `refactor(project-template): replace marker injection with wire_apps()`
5. `refactor(cli): shrink hatch.py — per-app knowledge lives in PhoxtailAppConfig`
6. `refactor(core): replace is_feature_enabled with app_installed + setting_enabled`
7. `test: update cli and engine tests for autonomous app wiring`
8. `docs: update migration guides for PhoxtailAppConfig`

Each commit is revertible independently. Phase 4 is the point of no return for the project template — if something goes wrong in 5–8, we can still operate because phases 1–3 are purely additive.

---

## 14. Fixed bug — `collect_url_patterns()` returned `[]`

> **Status**: Resolved.

### Symptom

`collect_url_patterns()` returned an empty list on every hatched project, so dashboard URLs never mounted and `/dashboard/` fell through to Wagtail's catch-all (404). `wire_apps()` itself worked correctly — only the URL collection path was broken.

### Root cause

Not class identity, not a stale install. The real cause was **Django's `AppConfig.create()` silently falling back to a plain `AppConfig`** for `phoxtail.dashboard` and `phoxtail.booking`.

Django scans each app's `apps.py` with `inspect.getmembers(mod, inspect.isclass)` and collects every `AppConfig` subclass found in the module's namespace. Because `phoxtail/dashboard/apps.py` does `from phoxtail.core.app_config import PhoxtailAppConfig`, *both* `PhoxtailAppConfig` and `PhoxtailDashboardConfig` appear as candidates. With two candidates and neither marked `default = True`, Django gives up on auto-selection and instantiates a plain `django.apps.AppConfig` instead — which has no `url_mount`, no `context_processors`, and is not a `PhoxtailAppConfig` instance.

Result: `isinstance(config, PhoxtailAppConfig)` in `collect_url_patterns()` was correctly `False` — the registered config genuinely wasn't one. The same bug affected every concrete `PhoxtailAppConfig` subclass that imported the base into its `apps.py`.

### Fix

In `phoxtail/core/app_config.py`, mark the base as `default = False` and auto-restore `default = True` on concrete subclasses via `__init_subclass__`:

```python
class PhoxtailAppConfig(AppConfig):
    default = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "default" not in cls.__dict__:
            cls.default = True
```

This excludes the imported base from Django's candidate list while ensuring every concrete subclass remains the single, unambiguous choice. No changes to the concrete `apps.py` files required.

### Verification

On the evolveyoupilates site after the fix:

```
phoxtail.dashboard | PhoxtailDashboardConfig | isinstance → True
phoxtail.booking   | PhoxtailBookingConfig   | isinstance → True
collect_url_patterns() → [<URLPattern 'dashboard/'>, ...]
```

`/dashboard/` resolves and the dashboard is reachable.
6. Re-run the verification checklist in §11.
