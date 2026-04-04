# Dashboard Migration Plan

Concrete plan to migrate the **dashboard** app from `phoxtail-project`
into the `phoxtail` library package, following the pattern established
by the **blog** migration.

---

## App overview

The dashboard is a **model-less, autodiscovery-based framework** that
provides a user-facing dashboard shell (sidebar, mobile dock/drawer,
widget grid). Other apps (like booking) register navigation items,
URL patterns, and widgets by dropping a `dashboard.py` file, which is
auto-discovered at startup.

### Files

| File | Purpose |
|------|---------|
| `apps.py` | `DashboardConfig` — runs `autodiscover_modules("dashboard")` in `ready()` |
| `registry.py` | `DashboardNavItem`, `DashboardWidget`, `DashboardModule`, `DashboardRegistry` singleton |
| `urls.py` | Root dashboard URL conf — index view + dynamic `registry.get_url_patterns()` |
| `views.py` | `dashboard_view` — collects widgets and renders the index page |
| `context_processors.py` | Injects `dashboard_nav_items` and `dashboard_mobile_nav_items` into every request |
| `templatetags/dashboard_tags.py` | Single tag: `{% dashboard_icon_path %}` → resolves SVG include path |
| `templates/dashboard/` | 4 templates: `base.html`, `index.html`, `navigation/{sidebar,dock,drawer}.html` |
| `static/dashboard/css/` | 2 CSS files: `dashboard.css` (layout), `ui.css` (components) |
| `docs/REGISTRATION.md` | Internal docs on the registration mechanism |

### Key characteristics

- **No models, no migrations** — pure Python + templates + static.
- **No third-party dependencies** beyond what `engine` already provides.
- **Autodiscovery pattern** — `autodiscover_modules("dashboard")` scans
  `INSTALLED_APPS` for `dashboard.py` modules (same pattern as Django
  admin).
- **Consumers**: Currently only `booking/core/dashboard.py` uses the
  registry. Future apps will follow the same pattern.
- **Template dependencies**: Templates load `core_tags` (→
  `phoxtail_core_tags`), `dashboard_tags`, `wagtailsettings_tags`,
  `wagtailimages_tags`, and `django_htmx`. They reference
  `core/svgs/*.html`, `core/css/*.css`, and `core/js/*.js` static files
  from `phoxtail.core`.
- **URL dependency**: `urls.py` includes `users.urls` — the `users` app
  is not yet migrated.

---

## Key differences from the blog migration

| Aspect | Blog | Dashboard |
|--------|------|-----------|
| Models | 3 (Page subclasses + snippet) | None |
| Migrations | 1 | None |
| Templates | 2 | 4 (shell/navigation) |
| Static files | None | 2 CSS files |
| URL patterns | Wagtail page routing | Custom URL conf with dynamic autodiscovery |
| Context processor | None | Yes — injects nav items on every request |
| Autodiscovery | None | Yes — `autodiscover_modules("dashboard")` |
| Template tags | 1 module | 1 module (`dashboard_tags`) |
| External consumers | None | Booking (and future apps) register modules |
| Third-party deps | Standard Wagtail | None beyond engine |
| Tests | N/A | None exist upstream |

---

## Migration strategy

The dashboard is a **framework app** — it has no models but provides
infrastructure that other apps depend on. This makes it a natural
prerequisite for the booking migration (booking's `dashboard.py` imports
from `dashboard.registry`).

**Recommendation**: Migrate dashboard first, then booking can import from
`phoxtail.dashboard.registry` instead of needing the dashboard
integration deferred.

---

## Step-by-step plan

### 1. Create the package structure

```
phoxtail/dashboard/
├── __init__.py
├── apps.py              # PhoxtailDashboardConfig
├── registry.py          # DashboardModule, DashboardRegistry, etc.
├── urls.py
├── views.py
├── context_processors.py
├── templatetags/
│   ├── __init__.py
│   └── phoxtail_dashboard_tags.py
├── templates/
│   └── phoxtail_dashboard/
│       ├── base.html
│       ├── index.html
│       └── navigation/
│           ├── sidebar.html
│           ├── dock.html
│           └── drawer.html
└── static/
    └── phoxtail_dashboard/
        └── css/
            ├── dashboard.css
            └── ui.css
```

### 2. AppConfig

```python
# phoxtail/dashboard/apps.py
from django.apps import AppConfig


class PhoxtailDashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.dashboard"
    label = "phoxtail_dashboard"
    verbose_name = "Phoxtail Dashboard"

    def ready(self):
        from django.utils.module_loading import autodiscover_modules

        autodiscover_modules("dashboard")
```

### 3. Copy registry.py as-is

The registry module is pure Python (dataclasses + a singleton class).
No imports need changing — it has zero external dependencies.

### 4. Rewrite imports in views.py and context_processors.py

| Upstream | Phoxtail |
|----------|----------|
| `from .registry import registry` | `from .registry import registry` (unchanged — relative) |
| `from dashboard.registry import registry` | `from phoxtail.dashboard.registry import registry` |

The views and context_processors already use relative imports, so they
need no changes. The `context_processors.py` uses an absolute import
(`from dashboard.registry`) — rewrite to relative (`from .registry`).

### 5. Handle the `users.urls` dependency in urls.py

The upstream `urls.py` includes:

```python
path("users/", include("users.urls", namespace="users")),
```

The `users` app is not yet migrated to phoxtail. Options:

- **(a)** Include a conditional import that only adds the users URL
  pattern if the users app is installed. This keeps the dashboard
  functional without the users app.
- **(b)** Leave the include as a string reference — Django will raise an
  error at URL resolution time only if the `users` app is missing, which
  is acceptable since the dashboard is optional.
- **(c)** Remove the users URL include entirely and let the project
  template wire it up.

**Recommendation**: Option (c) — the dashboard `urls.py` should only
include the index route and the dynamic `registry.get_url_patterns()`
routes. The `users/` URL should be configured in the project's root URL
conf (or in a future `phoxtail.users` app). This keeps the dashboard
decoupled from the users app.

```python
# phoxtail/dashboard/urls.py
from django.urls import include, path

from .registry import registry
from .views import dashboard_view

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_view, name="index"),
]

for url_prefix, url_patterns in registry.get_url_patterns():
    urlpatterns.append(
        path(url_prefix, include((url_patterns, url_prefix.strip("/"))))
    )
```

### 6. Rename template directory

`templates/dashboard/` → `templates/phoxtail_dashboard/`

Update all template references:

| Upstream | Phoxtail |
|----------|----------|
| `"dashboard/base.html"` | `"phoxtail_dashboard/base.html"` |
| `"dashboard/index.html"` | `"phoxtail_dashboard/index.html"` |
| `"dashboard/navigation/sidebar.html"` | `"phoxtail_dashboard/navigation/sidebar.html"` |
| `"dashboard/navigation/dock.html"` | `"phoxtail_dashboard/navigation/dock.html"` |
| `"dashboard/navigation/drawer.html"` | `"phoxtail_dashboard/navigation/drawer.html"` |

Also update `{% extends %}` and `{% include %}` tags within the
templates themselves.

### 7. Rename static directory

`static/dashboard/` → `static/phoxtail_dashboard/`

Update references in templates:

| Upstream | Phoxtail |
|----------|----------|
| `{% static 'dashboard/css/dashboard.css' %}` | `{% static 'phoxtail_dashboard/css/dashboard.css' %}` |
| `{% static 'dashboard/css/ui.css' %}` | `{% static 'phoxtail_dashboard/css/ui.css' %}` |

### 8. Rename template tags module

`dashboard_tags.py` → `phoxtail_dashboard_tags.py`

Update all `{% load dashboard_tags %}` in templates to
`{% load phoxtail_dashboard_tags %}`.

The `dashboard_icon_path` tag currently returns
`"core/svgs/{icon_name}.html"` — this references `phoxtail.core`'s
static templates. Verify these exist in `phoxtail/core/templates/core/svgs/`
or update the path to `phoxtail_core/svgs/{icon_name}.html` depending on
what the core app uses.

### 9. Update template tag loads in templates

The navigation templates load `core_tags` — update to
`phoxtail_core_tags` to match the library naming convention.

| Upstream | Phoxtail |
|----------|----------|
| `{% load core_tags dashboard_tags %}` | `{% load phoxtail_core_tags phoxtail_dashboard_tags %}` |

### 10. Handle hardcoded URL names in templates

The templates reference several URL names:

| URL name | Source |
|----------|--------|
| `dashboard:index` | Dashboard's own URL conf |
| `:users:profile` | `users` app — depends on users being wired |
| `dashboard:booking:events:list` | Booking registration via registry |
| `account_login` / `account_signup` / `account_logout` | `django-allauth` |
| `wagtailadmin_home` | Wagtail admin |

The `:users:profile` reference will break without the users
app. Options:

- **(a)** Wrap the profile link in `{% url ... as var %}` with a
  conditional (already done in the upstream template for sidebar/dock).
- **(b)** Guard the profile link with a feature flag or `{% if %}` check.
- **(c)** Leave it — the link only renders when the dashboard is active,
  and the users URL will be wired by the project.

**Recommendation**: Option (c) for now. The templates already use
`{% url ... as var %}` pattern. The profile link is expected to work
when dashboard is active, and the project template will wire
`users.urls` into the dashboard URL namespace.

The `dashboard:booking:events:list` reference in `index.html` is
hardcoded in the "Book a Class" button. This should be either:
- Removed (it's booking-specific and shouldn't live in a generic
  dashboard template).
- Made conditional on booking being installed.

**Recommendation**: Remove the hardcoded "Book a Class" button. The
dashboard home page should only show registered widgets — the button
belongs in a booking widget or nav item, not in the dashboard shell.

### 11. Register in pyproject.toml

```toml
[project.optional-dependencies]
dashboard = [
    "phoxtail[engine]",
]
dev = [
    "phoxtail[engine,blog,booking,dashboard,docs]",
]

[tool.setuptools.package-data]
"phoxtail.dashboard" = ["templates/**/*", "static/**/*"]
```

### 12. Make the app selectable during hatch

Update `OPTIONAL_APPS` in `phoxtail/cli/hatch.py`:

```python
OPTIONAL_APPS = [
    {"name": "Blog", "value": "phoxtail.blog"},
    {"name": "Dashboard", "value": "phoxtail.dashboard"},
    {"name": "Booking", "value": "phoxtail.booking"},
]
```

When "Dashboard" is selected, inject `"phoxtail.dashboard"` into
`INSTALLED_APPS`.

**Important**: If "Booking" is selected, "Dashboard" should be
auto-selected as a dependency (booking's `dashboard.py` imports from
the registry). This can be handled either:
- In the hatch wizard (auto-check Dashboard when Booking is checked).
- In `pyproject.toml` (make `booking` extra depend on
  `phoxtail[dashboard]`).

**Recommendation**: Handle in `pyproject.toml`:

```toml
booking = [
    "phoxtail[engine,dashboard]",
    ...
]
```

And in the hatch wizard, auto-add `"phoxtail.dashboard"` to
`INSTALLED_APPS` when booking is selected (even if not explicitly
checked).

### 13. Wire context processor in project template

The project template's `base.py` settings needs to include the
dashboard context processor when the dashboard app is selected:

```python
"phoxtail.dashboard.context_processors.dashboard_nav",
```

This should be injected by `_copy_template` alongside the
`INSTALLED_APPS` entries, using either a new marker in the settings
template or by having the dashboard app's `AppConfig.ready()` handle
it programmatically.

**Recommendation**: Add a
`# {{ phoxtail_context_processors }}` marker to the project template's
settings, similar to `# {{ phoxtail_optional_apps }}`. Or simpler:
always include the context processor in the template and let Django
handle the case where the app isn't installed (it will just do nothing).

### 14. Write tests

Since the upstream has no tests, write new ones:

- **Registry unit tests**: Test `DashboardModule`, `DashboardRegistry`,
  `add_nav_item`, `add_widget`, `register`, `get_nav_items`, ordering,
  duplicate registration error.
- **Template tag test**: Test `dashboard_icon_path` returns correct path.
- **Context processor test**: Test `dashboard_nav` returns the expected
  keys.

### 15. Lint and verify

```bash
make lint-check
make test
```

---

## Dependency on other migrations

| Dependency | Status | Impact |
|------------|--------|--------|
| `phoxtail.core` | Already migrated | Templates reference `phoxtail_core_tags`, `core/svgs/`, `core/css/`, `core/js/` |
| `phoxtail.users` | Not yet migrated | `users.urls` included in dashboard URL conf — handled by removing the include (step 5) |
| `phoxtail.booking` | Not yet migrated | Booking registers a dashboard module — this is fine since autodiscovery only runs for installed apps |

**Migration order**: Dashboard should be migrated **before** booking,
so booking's `dashboard.py` can import from
`phoxtail.dashboard.registry` directly.

---

## Checklist

- [ ] Create `phoxtail/dashboard/__init__.py`
- [ ] Create `phoxtail/dashboard/apps.py` with `PhoxtailDashboardConfig`
- [ ] Copy `registry.py` (no changes needed)
- [ ] Copy and update `views.py` (relative imports only — no changes)
- [ ] Copy and update `context_processors.py` (rewrite absolute import to relative)
- [ ] Copy and update `urls.py` (remove `users.urls` include)
- [ ] Rename template dir to `phoxtail_dashboard/`
- [ ] Update all `{% extends %}` and `{% include %}` paths in templates
- [ ] Rename static dir to `phoxtail_dashboard/`
- [ ] Update all `{% static %}` paths in templates
- [ ] Rename `dashboard_tags.py` → `phoxtail_dashboard_tags.py`
- [ ] Update all `{% load dashboard_tags %}` → `{% load phoxtail_dashboard_tags %}`
- [ ] Update all `{% load core_tags %}` → `{% load phoxtail_core_tags %}`
- [ ] Remove hardcoded "Book a Class" button from `index.html`
- [ ] Add `dashboard` optional extra in `pyproject.toml`
- [ ] Add package-data entry for `phoxtail.dashboard`
- [ ] Add `dashboard` to `dev` extra
- [ ] Add "Dashboard" to `OPTIONAL_APPS` in `hatch.py`
- [ ] Handle context processor injection in project template
- [ ] Ensure booking extra depends on `phoxtail[dashboard]`
- [ ] Write registry, template tag, and context processor tests
- [ ] Verify `phoxtail.core` SVG templates exist at expected paths
- [ ] `make lint-check && make test` — all green

---

## Open questions

1. **Users URL wiring**: Where should `users.urls` be included after
   dashboard drops it — in the project template's root URL conf, or
   should we wait for a `phoxtail.users` migration?

2. **Context processor injection**: Should we add a new marker in the
   project template for context processors, or always include the
   dashboard context processor (with graceful fallback if not installed)?

3. **SVG icon paths**: The `dashboard_icon_path` tag returns
   `"core/svgs/{icon}.html"`. Does `phoxtail.core` use the same path,
   or has it been renamed to `"phoxtail_core/svgs/{icon}.html"`?
