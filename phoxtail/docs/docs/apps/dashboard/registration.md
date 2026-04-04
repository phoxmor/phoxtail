# Dashboard App Registration Mechanism

## Overview

The dashboard app provides an autodiscovery-based registration mechanism that allows any Django app to contribute navigation items, URL patterns, and home-page widgets to the user-facing dashboard. This follows the same pattern as Django's `admin.py` autodiscovery and Wagtail's `wagtail_hooks.py`.

Each app that wants to integrate with the dashboard creates a `dashboard.py` module at its top level. The dashboard app discovers these modules at startup via `autodiscover_modules("dashboard")` in its `AppConfig.ready()` method.

## Design Rationale

- **Decoupled**: The dashboard app has zero knowledge of which apps register with it. Adding or removing an app requires no changes to dashboard code.
- **Feature-flagged**: Apps are gated behind feature flags in `INSTALLED_APPS`. If an app isn't installed, its `dashboard.py` is never discovered, so no nav items, URLs, or widgets appear.
- **Convention over configuration**: Drop a `dashboard.py` file in your app → it's automatically picked up.

## API Reference

### `DashboardNavItem`

A dataclass representing a navigation link in the dashboard sidebar.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `label` | `str` | required | Display text for the nav link |
| `url_name` | `str` | required | Django URL name (e.g. `"dashboard:booking:events:list"`) |
| `icon` | `str` | required | SVG filename (without extension) under `core/svgs/` |
| `order` | `int` | `100` | Sort order — lower values appear first |
| `mobile` | `bool` | `True` | Whether to show in the mobile bottom dock. When more than 3 mobile items are registered, the dock shows the first 2 + a "More" sheet for the rest. |

### `DashboardWidget`

A dataclass representing a widget on the dashboard home page.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `template_name` | `str` | required | Path to the widget's Django template |
| `context_function` | `callable` | required | Function `(request) → dict` providing template context |
| `order` | `int` | `100` | Sort order — lower values appear first |
| `css_files` | `list[str]` | `[]` | Static CSS file paths to load on the dashboard home page (deduplicated across widgets) |

### `DashboardModule`

Container for one app's dashboard contributions.

```python
module = DashboardModule(
    app_name="booking",       # unique key — duplicates raise ValueError
    url_prefix="booking/",    # mounted under /dashboard/booking/
    url_patterns=[...],       # list of path() objects
)
```

**Methods:**

- `add_nav_item(**kwargs)` — add a `DashboardNavItem` (accepts same fields)
- `add_widget(**kwargs)` — add a `DashboardWidget` (accepts same fields)

### `DashboardRegistry`

Singleton that collects all registered modules.

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `register(module)` | `None` | Register a module (raises `ValueError` on duplicate `app_name`) |
| `get_nav_items()` | `list[DashboardNavItem]` | All nav items, sorted by order |
| `get_mobile_nav_items()` | `list[DashboardNavItem]` | Only items with `mobile=True`, sorted by order. Used by the bottom dock. |
| `get_url_patterns()` | `list[tuple]` | `(url_prefix, url_patterns)` pairs for URL mounting |
| `get_widgets()` | `list[DashboardWidget]` | All widgets, sorted by order |
| `get_widget_css_files()` | `list[str]` | Deduplicated CSS file paths from all registered widgets |

### Module-level instance

```python
from dashboard.registry import registry
```

Always import and use this singleton — do not create new `DashboardRegistry` instances.

## How to Write a `dashboard.py` File

### Step-by-step

1. Create `your_app/dashboard.py` (or `your_app/core/dashboard.py` for multi-module apps)
2. Import the registry and module class
3. Create a `DashboardModule` with your app's URL patterns
4. Add nav items and widgets
5. Register the module

### Example

```python
# myapp/dashboard.py
from django.urls import include, path

from dashboard.registry import DashboardModule, registry

module = DashboardModule(
    app_name="myapp",
    url_prefix="myapp/",
    url_patterns=[
        path("items/", include("myapp.urls")),
    ],
)

module.add_nav_item(
    label="My Items",
    url_name="dashboard:myapp:items:list",
    icon="browse",
    order=10,
    # mobile=True is the default — item appears in both sidebar and mobile dock.
    # Set mobile=False for admin-only or rarely-used items to keep the dock uncluttered.
)


def get_recent_items(request):
    from myapp.models import Item

    items = Item.objects.filter(user=request.user).order_by("-created_at")[:5]
    return {"items": items}


module.add_widget(
    template_name="myapp/dashboard/widgets/recent_items.html",
    context_function=get_recent_items,
    order=10,
    css_files=["myapp/css/public.css"],
)

registry.register(module)
```

### Widget template example

```html
{# myapp/templates/myapp/dashboard/widgets/recent_items.html #}
<div class="dash-widget-card">
    <h3 class="dash-widget-title">Recent Items</h3>
    {% if data.items %}
        <ul class="dash-widget-list">
            {% for item in data.items %}
                <li class="dash-widget-list__item">
                    <div class="dash-widget-list__primary">
                        {{ item.name }}
                    </div>
                </li>
            {% endfor %}
        </ul>
    {% else %}
        <p class="dash-widget-empty">No items yet.</p>
    {% endif %}
</div>
```

Widget templates receive the context function's return dict merged into the template context under `data`.

## URL Mounting and Namespace Structure

URL patterns from registered modules are mounted under the dashboard's URL prefix:

```
/dashboard/                          → dashboard:index
/dashboard/users/profile/            → :users:profile
/dashboard/<url_prefix>/<app_urls>   → dashboard:<url_prefix_stripped>:<url_name>
```

For the booking example:

```
/dashboard/booking/events/           → dashboard:booking:events:list
/dashboard/booking/services/         → dashboard:booking:services:list
/dashboard/booking/reservations/     → dashboard:booking:reservations:list
/dashboard/booking/subscriptions/    → dashboard:booking:subscriptions:subscription-list
```

The namespace is derived from `url_prefix.strip("/")`, so `url_prefix="booking/"` creates the `booking` namespace.

## How Autodiscovery Works

1. Django starts → `DashboardConfig.ready()` fires
2. `autodiscover_modules("dashboard")` scans all `INSTALLED_APPS` for a `dashboard` module
3. Each discovered `dashboard.py` executes, calling `registry.register(module)`
4. By the time URL conf loads, all modules are registered
5. `dashboard/urls.py` iterates `registry.get_url_patterns()` to mount dynamic URL patterns
6. `dashboard/context_processors.py` injects two template variables on every request:
   - `dashboard_nav_items` — all registered items, used by the desktop sidebar and mobile drawer
   - `dashboard_mobile_nav_items` — only items with `mobile=True`, used by the mobile bottom dock
7. `dashboard/views.py` collects widget data on the home page

## How Feature Flags Gate App Inclusion

In `src/settings/base.py`:

```python
FEATURE_ACTIVATE_BOOKING = env.bool("FEATURE_ACTIVATE_BOOKING", default=False)

if FEATURE_ACTIVATE_BOOKING:
    INSTALLED_APPS += [
        "booking.core",
        "booking.services",
        "booking.events",
        "booking.subscriptions",
        "booking.reservations",
    ]
```

When `FEATURE_ACTIVATE_BOOKING=False`:
- Booking apps are not in `INSTALLED_APPS`
- `autodiscover_modules` never finds `booking.core.dashboard`
- No booking nav items, URLs, or widgets are registered
- No import errors — the booking code is never loaded

## CSS Classes

All dashboard templates use pure CSS with the `dash-` prefix. The full set of classes is
defined and commented in `dashboard/static/dashboard/css/dashboard.css` — that file is the
authoritative reference.

Classes most relevant to widget authors:

| Class | Purpose |
|-------|---------|
| `dash-widget-card` | Widget card container |
| `dash-widget-title` | Widget heading |
| `dash-widget-empty` | Empty state text inside a widget |
| `dash-widgets-grid` | Responsive grid that wraps widget cards |
| `dash-widget-list` | Container for list items inside a card |
| `dash-widget-list__item` | A single row in a widget list |
| `dash-widget-list__primary` | Primary text (semibold) in a list item |
| `dash-widget-list__secondary` | Secondary text (muted) in a list item |
| `dash-empty-state` | Full-page empty state (icon + heading + text) |

Classes used by the navigation shell (provided automatically, not needed in widget templates):

| Class | Purpose |
|-------|---------|
| `dash-nav-item` / `dash-nav-item--active` | Sidebar and drawer link rows |
| `dash-nav-icon` / `dash-nav-label` | Icon and label inside a nav row |
| `dash-nav-signout` | Sign out button variant of `dash-nav-item` |
| `dash-nav-separator` | Horizontal rule between nav groups |
| `dash-dock__item` / `dash-dock__item--active` | Bottom dock tab items |
| `dash-dock-sheet` / `dash-dock-sheet--open` | Overflow "More" sheet above the dock |

All classes consume CSS custom properties from `core/static/core/css/main.css`
(e.g. `rgb(var(--color-primary-600))`), which are overridden at runtime by
`SiteConfig.css_variables`. See `app/docs/design-tokens-architecture.md` for the full
token injection flow.
