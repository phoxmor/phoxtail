# Migrating a Library App to Its Own Package

Some apps were built inside the phoxtail library not because they belong there architecturally, but because it was the practical place to develop them when the ecosystem was young. The booking cluster is the primary example. This guide covers how to extract such an app (or cluster of apps) into its own standalone package.

The structural move is mechanical. The real cost is usually that library-era apps predate the manifesto standard — no Django Ninja API, no MCP tools. Treat extraction as the moment to close that gap.

---

## Before You Start

Read [What Makes a Phoxtail App](phoxtail-app-manifesto.md). The goal of extraction is not just a different folder — it is a fully compliant phoxtail app that self-wires, exposes a uniform API, ships MCP tools, and centralises its logic in a service layer. Extracting without meeting that standard produces a package that is external but still second-class.

---

## Step 1: Create the new package

Create a new repository (or a new top-level directory in a monorepo) with the following structure:

```
phoxtail-booking/
├── pyproject.toml
├── README.md
└── phoxtail_booking/
    ├── __init__.py
    ├── core/
    ├── events/
    ├── reservations/
    ├── services/
    └── subscriptions/
```

The Python package name uses underscores (`phoxtail_booking`); the distribution name uses hyphens (`phoxtail-booking`). This matches the convention established by `phoxtail_templates` and every other site-level app.

---

## Step 2: Write `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "phoxtail-booking"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "phoxtail>=<minimum version>",
    "celery",
    "django-celery-beat",
]

[project.entry-points."phoxtail.mcp_modules"]
booking = "phoxtail_booking.mcp"

[tool.setuptools.packages.find]
include = ["phoxtail_booking*"]
```

The `phoxtail.mcp_modules` entry point is what makes MCP tools discoverable on the host without Django. Declare it from the start even if the `mcp/` module is a stub.

---

## Step 3: Move the code — keep the Django labels identical

This is the one step where a mistake causes lasting damage. Django migrations are tied to the app `label`, not the Python path. If you rename a label, every existing migration and every existing database table breaks.

The rule: **the Python path can change freely; the `label` must not.**

For the booking cluster, this means:

| Before (library) | After (package) | Label — must not change |
|---|---|---|
| `phoxtail.booking.core` | `phoxtail_booking.core` | `phoxtail_booking_core` |
| `phoxtail.booking.events` | `phoxtail_booking.events` | `phoxtail_booking_events` |
| `phoxtail.booking.reservations` | `phoxtail_booking.reservations` | `phoxtail_booking_reservations` |
| `phoxtail.booking.services` | `phoxtail_booking.services` | `phoxtail_booking_services` |
| `phoxtail.booking.subscriptions` | `phoxtail_booking.subscriptions` | `phoxtail_booking_subscriptions` |

Verify each `apps.py` explicitly sets `label =` to the stable value. Do not rely on Django inferring it from the package name, since the package name changed.

Move the migrations directory with each sub-app. Do not regenerate migrations. Existing migration history must travel with the code intact.

---

## Step 4: Update `apps.py` on each sub-app

Each sub-app's `PhoxtailAppConfig` needs its `name` updated to the new Python path, its `label` left unchanged, and its library cross-references audited.

```python
# Before
class PhoxtailBookingCoreConfig(PhoxtailAppConfig):
    name = "phoxtail.booking.core"
    label = "phoxtail_booking_core"

# After
class PhoxtailBookingCoreConfig(PhoxtailAppConfig):
    name = "phoxtail_booking.core"
    label = "phoxtail_booking_core"   # unchanged
```

The top-level cluster config (`apps.py` at the root of the package) updates its `depends_on` list to reference the new paths:

```python
class PhoxtailBookingConfig(PhoxtailAppConfig):
    name = "phoxtail_booking"
    label = "phoxtail_booking"
    depends_on = [
        "phoxtail.dashboard",
        "phoxtail_booking.core",
        "phoxtail_booking.events",
        "phoxtail_booking.subscriptions",
        "phoxtail_booking.reservations",
        "phoxtail_booking.services",
        "django_celery_beat",
    ]
    requires_celery = True
```

---

## Step 5: Audit imports — distinguish framework from peer

The extracted package will import from phoxtail. Not all imports are equal.

**Framework imports — fine, these are the contract:**
```python
from phoxtail.core.app_config import PhoxtailAppConfig
from phoxtail.core.mixins import UUIDMixin, TimestampMixin
from phoxtail.core.permissions import ...
from phoxtail.core.views import ...
from phoxtail.core.fields import ...
```

**Peer imports — these become `depends_on` declarations:**
```python
from phoxtail.dashboard.registry import ...   # depends_on = ["phoxtail.dashboard"]
from phoxtail.design.models import ...         # depends_on = ["phoxtail.design"]
from phoxtail.users.models import ...          # depends_on = ["phoxtail.users"]
from phoxtail.users.services import ...        # depends_on = ["phoxtail.users"]
```

No import statements change — the phoxtail library is now an installed dependency. What changes is that these are now explicit in both `depends_on` (for runtime wiring) and `pyproject.toml` `dependencies` (for install-time resolution).

---

## Step 6: Add the API surface (if missing)

Library-era apps often used DRF viewsets rather than the Django Ninja pattern. Extraction is the right moment to migrate.

For each sub-app that owns data, create `api/v1/`:

```
phoxtail_booking/events/
└── api/
    └── v1/
        ├── __init__.py
        ├── router.py       # ninja.Router instance
        ├── schemas.py      # Pydantic in/out schemas
        └── endpoints.py    # route handlers
```

Declare the router in `apps.py`:

```python
class PhoxtailBookingEventsConfig(PhoxtailAppConfig):
    name = "phoxtail_booking.events"
    label = "phoxtail_booking_events"
    api_version_router = "phoxtail_booking.events.api.v1.router"
```

The framework mounts it at `/api/booking_events/v1/` automatically. No changes to central routing.

---

## Step 7: Add MCP tools (if missing)

Create `mcp/` alongside `api/`:

```
phoxtail_booking/
└── mcp/
    ├── __init__.py
    ├── events.py       # tool definitions
    └── reservations.py
```

`__init__.py` simply imports the tool modules — no gate needed:

```python
# phoxtail_booking/mcp/__init__.py
from phoxtail_booking.mcp import events       # noqa: F401
from phoxtail_booking.mcp import reservations  # noqa: F401
```

A standalone package is only installed when a project explicitly depends on it. Installation is the opt-in signal — a `phoxtail.toml` gate is the library-era pattern for filtering inactive apps out of a monolithic wheel, and does not apply here. The `phoxtail.mcp_modules` entry point in `pyproject.toml` is the discovery mechanism; it fires because the package is installed, which already implies the project uses it.

---

## Step 8: Remove the hard-coded reference in the library

If the library's CLI `hatch.py` (or any equivalent scaffolding command) lists the app as a built-in option, remove it. The library should not know about packages it does not ship. The extracted package can document its own install instructions.

---

## Step 9: Install the new package in projects that use it

**Make the package importable.** Until published to PyPI, the practical options are:

- **Bind mount** (local/dev): mount the package directory into the container alongside the phoxtail library and cover it with the same `PYTHONPATH`. No pip install needed.
- **Git URL** (pre-PyPI, any environment): `pip install git+https://github.com/phoxmor/phoxtail-booking.git` in the project's requirements. Works once the repo is pushed — including private repos with SSH keys or token auth. Transitions to a plain version specifier once published.
- **PyPI** (published): `phoxtail-booking>=0.1.0`

**Add to `INSTALLED_APPS`** in the project's settings:

```python
INSTALLED_APPS = [
    ...
    "phoxtail_booking",
]
```

`wire_apps` reads from `INSTALLED_APPS` — it resolves `depends_on` transitively from whatever you list there, but does not read `phoxtail.toml`. The top-level app must be explicitly present.

`phoxtail.toml → [project].apps` does **not** need the new app. That list is only used by CLI commands (like `phoxtail hatch`) and is not part of the Django wiring path. MCP tools are discovered via the `phoxtail.mcp_modules` entry point automatically when the package is installed.

---

## Checklist

- [ ] New package created with correct `pyproject.toml`
- [ ] `phoxtail.mcp_modules` entry point declared (even if `mcp/` is a stub)
- [ ] All sub-app `label` values verified unchanged
- [ ] All sub-app `name` values updated to new Python path
- [ ] Migrations moved intact — not regenerated
- [ ] Peer imports audited and declared in `depends_on` + `pyproject.toml`
- [ ] Django Ninja API surface added or confirmed existing
- [ ] MCP tools added or confirmed existing
- [ ] MCP `__init__.py` imports tool modules directly — no `get_project_apps()` gate
- [ ] Hard-coded library reference removed from `hatch.py` or equivalent
- [ ] Package made importable in each project (bind mount, git URL, or PyPI)
- [ ] `"phoxtail_<app>"` added to `INSTALLED_APPS` in each project's settings
