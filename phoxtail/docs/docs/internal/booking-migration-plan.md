# Booking Cluster Migration Plan

Concrete plan to migrate the **booking** app cluster from
`phoxtail-project` into the `phoxtail` library package, following the
pattern established by the **blog** migration.

---

## Cluster overview

The upstream booking system is a cluster of **5 tightly coupled Django
apps** (not one app like blog):

| App | Label (upstream) | Models | Key role |
|-----|-----------------|--------|----------|
| `booking.core` | `booking_core` | BookingGroup, Location, Space, Staff, BookingAdminPermission | Shared entities, permissions, admin settings, dashboard |
| `booking.services` | `booking_services` | Service | Service catalogue (e.g. "Pilates Mat Class") |
| `booking.events` | `booking_events` | Event, EventGenerationSchedule, EventGenerationScheduleExclusion, EventGenerationScheduleExclusionPeriod | Scheduled event instances, Celery tasks, recurrence |
| `booking.subscriptions` | `booking_subscriptions` | SubscriptionType, SubscriptionTypeCreditAllocation, Subscription, SubscriptionCreditBalance | Plans, credits, billing |
| `booking.reservations` | `booking_reservations` | Reservation | User bookings for events |

### Dependency graph (model-level FKs)

```
core ← services ← events ← reservations
  ↑                  ↑           ↑
  └── subscriptions ─┘───────────┘
```

- `events.models` imports from `core.models` and `services.models`
- `subscriptions.models` imports from `core.models` and `services.models`
- `reservations.models` imports from `events.models` and `subscriptions.models`

### Scale

| Metric | Count |
|--------|-------|
| Python files (non-init, non-migration) | ~138 |
| HTML templates | ~120 |
| CSS files | 8 |
| Migration files | 11 |
| Test files | 31 |

---

## Key differences from the blog migration

| Aspect | Blog | Booking |
|--------|------|---------|
| Number of Django apps | 1 | 5 (inter-dependent) |
| Models | Wagtail Pages (BlogIndexPage, BlogPostPage) + 1 snippet | Pure Django models (no Page subclasses) |
| Cross-app imports | None | Heavy — every sub-app imports from core/services |
| URL routing | Wagtail page routing | Custom dashboard module + URL patterns |
| External deps | Standard Wagtail | `django-countries`, `phonenumber-field`, `timezone-field`, `django-celery-beat`, `django-filter` |
| Dashboard integration | None | `dashboard.registry` module |
| Permissions system | None | Custom `BookingAdminPermission` + permission policy |
| Celery tasks | None | `events/tasks.py` for recurring event generation |
| Admin views | Wagtail admin only | Custom admin views (settings, users, booking, scheduling, billing) |
| Service layer | None | Deep service/operation/gateway pattern per sub-app |
| Static files | None | CSS for reservations, events, subscriptions, core |
| Template tags | 1 module | 1 module (`events_tags`) |
| Block data | 4 blocks | 1 block (`booking_schedule` — currently in `streams/`) |

---

## Migration strategy

### Single optional extra, five sub-apps

Install as one extra `phoxtail[booking]` that pulls in all five sub-apps.
They are not independently useful — you can't have reservations without
events, subscriptions, services, and core.

```
phoxtail/booking/
├── __init__.py
├── core/
├── services/
├── events/
├── subscriptions/
└── reservations/
```

All five apps get injected into `INSTALLED_APPS` as a group when the user
selects "Booking" during hatch.

---

## Step-by-step plan

### 1. Create the package structure

Create `phoxtail/booking/` with the five sub-apps mirroring the upstream
layout. Rename AppConfig values:

| Field | Upstream | Phoxtail |
|-------|----------|----------|
| `core AppConfig.name` | `booking.core` | `phoxtail.booking.core` |
| `core AppConfig.label` | `booking_core` | `phoxtail_booking_core` |
| `services AppConfig.name` | `booking.services` | `phoxtail.booking.services` |
| `services AppConfig.label` | `booking_services` | `phoxtail_booking_services` |
| `events AppConfig.name` | `booking.events` | `phoxtail.booking.events` |
| `events AppConfig.label` | `booking_events` | `phoxtail_booking_events` |
| `subscriptions AppConfig.name` | `booking.subscriptions` | `phoxtail.booking.subscriptions` |
| `subscriptions AppConfig.label` | `booking_subscriptions` | `phoxtail_booking_subscriptions` |
| `reservations AppConfig.name` | `booking.reservations` | `phoxtail.booking.reservations` |
| `reservations AppConfig.label` | `booking_reservations` | `phoxtail_booking_reservations` |

### 2. Rewrite all imports

Every `from booking.X` becomes `from phoxtail.booking.X`. Every
`from core.mixins` becomes `from phoxtail.core.mixins`. Every
`from core.permissions` becomes `from phoxtail.core.permissions`.

The `design.Palette` FK in `services/models.py` becomes
`"phoxtail_design.Palette"` (string reference to avoid circular imports).

Full import rewrite map:

| Upstream import | Phoxtail import |
|----------------|-----------------|
| `from booking.core.models import ...` | `from phoxtail.booking.core.models import ...` |
| `from booking.services.models import ...` | `from phoxtail.booking.services.models import ...` |
| `from booking.events.models import ...` | `from phoxtail.booking.events.models import ...` |
| `from booking.subscriptions.models import ...` | `from phoxtail.booking.subscriptions.models import ...` |
| `from booking.reservations.models import ...` | `from phoxtail.booking.reservations.models import ...` |
| `from core.mixins import ...` | `from phoxtail.core.mixins import ...` |
| `from core.permissions import ...` | `from phoxtail.core.permissions import ...` |
| `from design.models import Palette` | `from phoxtail.design.models import Palette` |
| `from dashboard.registry import ...` | `from phoxtail.dashboard.registry import ...` |

### 3. Rewrite template directories

Upstream templates live under app-label directories (e.g.
`templates/booking_core/`, `templates/events/`, `templates/reservations/`,
`templates/services/`, `templates/subscriptions/`).

Rename to avoid collisions with user-project templates:

| Upstream | Phoxtail |
|----------|----------|
| `templates/booking_core/` | `templates/phoxtail_booking_core/` |
| `templates/events/` | `templates/phoxtail_booking_events/` |
| `templates/reservations/` | `templates/phoxtail_booking_reservations/` |
| `templates/services/` | `templates/phoxtail_booking_services/` |
| `templates/subscriptions/` | `templates/phoxtail_booking_subscriptions/` |

Update all `template_name` references in views and `template` attributes
in code to match.

### 4. Rename template tags module

Upstream `events_tags` becomes `phoxtail_booking_events_tags` to avoid
collisions. Update all `{% load events_tags %}` references in templates.

### 5. Rename static file directories

| Upstream | Phoxtail |
|----------|----------|
| `static/booking_core/` | `static/phoxtail_booking_core/` |
| `static/events/` | `static/phoxtail_booking_events/` |
| `static/reservations/` | `static/phoxtail_booking_reservations/` |
| `static/services/` | `static/phoxtail_booking_services/` |
| `static/subscriptions/` | `static/phoxtail_booking_subscriptions/` |

Update all `css_files` references in dashboard.py and any template
`{% static %}` tags.

### 6. Handle the dashboard module

The upstream `booking/core/dashboard.py` imports from
`dashboard.registry`. The dashboard app should be migrated first (see
[dashboard-migration-plan.md](dashboard-migration-plan.md)), so by the
time booking is migrated, the registry will live at
`phoxtail.dashboard.registry`.

Rewrite `booking/core/dashboard.py`:

```python
from phoxtail.dashboard.registry import DashboardModule, registry
```

Also update all template name references in the dashboard module
(widget templates, CSS paths) to use the `phoxtail_booking_*` prefixed
paths.

### 7. Handle permissions

The `core/permissions/setup.py` imports from `core.permissions` (the
upstream project's permission framework), which maps to
`phoxtail.core.permissions` in the library. This is already available:

- `phoxtail.core.permissions.policies` → `AppPermissionPolicy`
- `phoxtail.core.permissions.viewsets` → `PermissionedViewSet`
- `phoxtail.core.permissions.mixins` → `PermissionMixin`
- `phoxtail.core.permissions.decorators` → `permission_required_factory`

Rewrite `booking/core/permissions/setup.py` to import from
`phoxtail.core.permissions` sub-modules.

### 8. Handle Celery tasks

`events/tasks.py` uses `@shared_task` from Celery and references
`booking.events.models`. Rewrite the import to
`phoxtail.booking.events.models`. The `celery` dependency is already in
the `engine` extra.

The `EventGenerationSchedule.sync_to_periodic_task()` references the task
path as `"booking.events.tasks.generate_recurring_events_task"` — update
to `"phoxtail.booking.events.tasks.generate_recurring_events_task"`.

### 9. Handle management commands

The `core/management/commands/` directory has 10 management commands for
populating booking data. Two of them import `from design.models import
Palette`, which becomes `from phoxtail.design.models import Palette`.

Move all management commands as-is, rewriting imports.

### 10. Move block data

The `booking_schedule` block currently lives in
`phoxtail/streams/management/data/blocks/booking_schedule/`. Move it to
`phoxtail/booking/events/management/data/blocks/booking_schedule/`
(since it references `booking_core.Location` and logically belongs to
the events sub-app).

Update the `target_model` in `schema.json` from `booking_core.Location`
to `phoxtail_booking_core.Location`.

### 11. Write new migrations

Squash upstream migrations into fresh `0001_initial.py` per sub-app.
Order matters due to FKs:

1. `phoxtail.booking.core` — no FK deps on other booking apps
2. `phoxtail.booking.services` — FK to `phoxtail_design.Palette`
3. `phoxtail.booking.events` — FKs to core + services
4. `phoxtail.booking.subscriptions` — FKs to core + services
5. `phoxtail.booking.reservations` — FKs to events + subscriptions

Use `dependencies` in each migration to declare cross-app FK
requirements.

### 12. Add third-party dependencies

The booking cluster requires packages not currently in the `engine`
extra:

| Package | Used by |
|---------|---------|
| `django-countries` | `core/models.py` (CountryField) |
| `phonenumber-field` | `core/models.py` (PhoneNumberField) |
| `django-timezone-field` | `core/models.py` (TimeZoneField) |
| `django-celery-beat` | `events/models.py` (PeriodicTask) |
| `django-filter` | `events/filters.py`, `subscriptions/filters.py` |

Add these to the `booking` optional extra in `pyproject.toml`:

```toml
booking = [
    "phoxtail[engine]",
    "django-countries>=7.0",
    "django-phonenumber-field[phonenumbers]>=7.0",
    "django-timezone-field>=6.0",
    "django-celery-beat>=2.5",
    "django-filter>=23.0",
]
```

### 13. Register in pyproject.toml

```toml
[project.optional-dependencies]
booking = [
    "phoxtail[engine]",
    "django-countries>=7.0",
    "django-phonenumber-field[phonenumbers]>=7.0",
    "django-timezone-field>=6.0",
    "django-celery-beat>=2.5",
    "django-filter>=23.0",
]
dev = [
    "phoxtail[engine,blog,booking,docs]",
]

[tool.setuptools.package-data]
"phoxtail.booking.core" = ["templates/**/*", "static/**/*"]
"phoxtail.booking.events" = ["templates/**/*", "static/**/*", "management/data/**/*"]
"phoxtail.booking.services" = ["templates/**/*", "static/**/*"]
"phoxtail.booking.subscriptions" = ["templates/**/*", "static/**/*"]
"phoxtail.booking.reservations" = ["templates/**/*", "static/**/*"]
```

### 14. Make the app selectable during hatch

Update `OPTIONAL_APPS` in `phoxtail/cli/hatch.py`:

```python
OPTIONAL_APPS = [
    {"name": "Blog", "value": "phoxtail.blog"},
    {"name": "Booking", "value": "phoxtail.booking"},
]
```

Hatch writes the single dotted name `"phoxtail.booking"` into the
generated project's `INSTALLED_APPS`. At Django startup, `wire_apps()`
finds the umbrella `PhoxtailBookingConfig` in `phoxtail/booking/apps.py`
and expands its `depends_on` list — `phoxtail.dashboard` plus the five
booking sub-apps plus `django_celery_beat` — into `INSTALLED_APPS`.

Because `PhoxtailBookingConfig.requires_celery = True` and its
`requirements = ["celery", "django-celery-beat"]`, hatch also:

- Appends celery + django-celery-beat to the generated
  `requirements.in`.
- Copies `src/celery.py` into the project (gated by the
  `CONDITIONAL_FILES` predicate in `hatch.py`).

At runtime, `wire_apps()` sets `PHOXTAIL_CELERY_ENABLED = True`, which
the generated settings modules use to switch on the Celery config
block.

### 15. Copy tests

Move all test files, factories, and conftest.py files. Rewrite all
imports. Add `phoxtail/booking/*/tests` to `testpaths` in
`pyproject.toml`. Tests depend on a Django test database with all five
booking apps installed. The test settings module pattern is:

```python
# src/settings/test.py
from .base import *  # noqa
INSTALLED_APPS += ["phoxtail.booking"]
from phoxtail.core.wiring import wire_apps
wire_apps(globals())
```

### 16. Update hatch tests

- Mock `questionary.checkbox` to return `["phoxtail.booking"]`.
- Verify that the rendered `INSTALLED_APPS` contains the single
  `"phoxtail.booking"` dotted name (not an expanded sub-app list).
- Verify that `src/celery.py` is copied when booking is selected and
  skipped otherwise.
- Verify that `requirements.in` contains `celery` and
  `django-celery-beat` when booking is selected and omits them
  otherwise.

### 17. Lint and verify

```bash
make lint-check
make test
```

---

## Checklist

- [ ] Create `phoxtail/booking/__init__.py`
- [ ] Create `phoxtail/booking/core/` with AppConfig `phoxtail.booking.core`
- [ ] Create `phoxtail/booking/services/` with AppConfig `phoxtail.booking.services`
- [ ] Create `phoxtail/booking/events/` with AppConfig `phoxtail.booking.events`
- [ ] Create `phoxtail/booking/subscriptions/` with AppConfig `phoxtail.booking.subscriptions`
- [ ] Create `phoxtail/booking/reservations/` with AppConfig `phoxtail.booking.reservations`
- [ ] Rewrite all `from booking.*` imports to `from phoxtail.booking.*`
- [ ] Rewrite all `from core.mixins` to `from phoxtail.core.mixins`
- [ ] Rewrite all `from core.permissions` to `from phoxtail.core.permissions`
- [ ] Rewrite `from design.models` to `from phoxtail.design.models`
- [ ] Rename template directories to `phoxtail_booking_*` prefix
- [ ] Rename static directories to `phoxtail_booking_*` prefix
- [ ] Rename `events_tags` templatetag module to `phoxtail_booking_events_tags`
- [ ] Move `booking_schedule` block from `streams/` to `booking/events/management/data/blocks/`
- [ ] Update `booking_schedule` schema `target_model` to `phoxtail_booking_core.Location`
- [ ] Write fresh `0001_initial.py` for each sub-app (in dependency order)
- [ ] Add third-party deps to `booking` extra in `pyproject.toml`
- [ ] Add package-data entries for all five sub-apps
- [ ] Add `booking` to `dev` extra
- [ ] Add "Booking" entry to `OPTIONAL_APPS` in `hatch.py`
- [ ] Update `_copy_template` to expand booking into five sub-app entries
- [ ] Rewrite `core/dashboard.py` to import from `phoxtail.dashboard.registry`
- [ ] Update Celery task path in `EventGenerationSchedule.sync_to_periodic_task()`
- [ ] Update Wagtail snippet URL names in admin settings views
- [ ] Copy and rewrite all tests
- [ ] Mock `questionary.checkbox` in hatch tests
- [ ] `make lint-check && make test` — all green

---

## Prerequisites

- **Dashboard must be migrated first.** Booking's `core/dashboard.py`
  imports from `dashboard.registry`. See
  [dashboard-migration-plan.md](dashboard-migration-plan.md). Once
  dashboard lives at `phoxtail.dashboard`, booking's dashboard module
  can import from `phoxtail.dashboard.registry` directly.

---

## Open questions

1. **Wagtail snippet registration**: The upstream uses `wagtail_hooks.py`
   (via viewsets.py) to register snippets with labels like
   `booking_core_location`. These will change to
   `phoxtail_booking_core_location`. The admin settings view hardcodes
   these URL names — all need updating.

2. **Hatch expansion**: How should a single "Booking" selection expand
   into 5 INSTALLED_APPS entries? Options: (a) modify `_copy_template`
   to support app groups, or (b) use a mapping dict in hatch.py.
