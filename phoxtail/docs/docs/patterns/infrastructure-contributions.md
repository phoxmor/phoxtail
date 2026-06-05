# Infrastructure Contributions

Phoxtail apps own their entire vertical slice — models, API, MCP tools,
and **infrastructure**. An app that needs a message broker, a background
worker, or any other sidecar process ships that requirement as a compose
fragment. `phoxtail docker create compose` discovers and merges fragments
automatically from whatever wheels are present in the project's `wheels/`
directory. The project author does not need to know what services an app
requires.

---

## The principle

Docker services cannot be delivered by `pip install`. A wheel installs
Python code; it does not create containers. But the *definition* of what
services an app needs is knowledge the app owns — not the project, and
not the phoxtail library.

The compose fragment pattern resolves this: the app ships its service
definitions as a Jinja2 template inside its wheel. The CLI discovers,
renders, and merges them at project configuration time. Infrastructure
ownership stays with the app; the project stays declarative.

This mirrors the pattern used for API routers and MCP tools:

| Contribution | Mechanism | Discovery runtime |
|---|---|---|
| API router | `PhoxtailAppConfig.api_version_router` | Django backend |
| MCP tools | `phoxtail.mcp_modules` entry point | Host (no Django) |
| Compose services | `deploy/compose.yaml.j2` convention | Host CLI (`wheels/` scan) |

---

## The convention

An app contributes a compose fragment by placing a Jinja2 template at
this path inside its package:

```
{top_package}/deploy/compose.yaml.j2
```

For `phoxtail-booking`:

```
phoxtail_booking/deploy/compose.yaml.j2
```

`phoxtail docker create compose` opens every non-phoxtail wheel in the
project's `wheels/` directory as a zip archive, checks for this path,
renders any it finds, and merges the result into the generated
`docker-compose.yaml`.

No entry point registration is required. The path is the declaration.

---

## The Jinja2 context

Fragments are rendered with the same context as the base compose
template. These keys are guaranteed:

| Key | Type | Example |
|---|---|---|
| `image_name` | `str` | `myorg/myproject:latest` |
| `environment` | `str` | `development` or `production` |
| `postgres_version` | `str` | `18` |
| `pg_data_path` | `str` | `/var/lib/postgresql/data` |

Use `image_name` for any service that must run the project's own
image (workers, beat schedulers). Use `environment` to switch
behaviour between development and production.

---

## Fragment rules

A fragment must declare only `services:` and/or `volumes:` keys. It
must not modify existing services (`web`, `db`, `docs`, `nginx`,
`certbot`). The merge is additive: new services and volumes are
appended to the base; existing ones are never touched.

Fragments that violate the additive rule will silently overwrite base
services, producing a broken compose file. Keep fragments self-contained.

---

## Complete example: phoxtail-booking

`phoxtail-booking` needs Redis as a message broker plus a Celery worker
and beat scheduler. Its fragment:

```yaml
# phoxtail_booking/deploy/compose.yaml.j2

services:
  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  celery-worker:
    build:
      target: {{ environment }}
    image: {{ image_name }}
    pull_policy: build
    restart: always
    user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
    volumes:
      - .:/app
    env_file:
      - ./.env
    command: celery -A src worker --loglevel=info
    depends_on:
      - db
      - redis

  celery-beat:
    build:
      target: {{ environment }}
    image: {{ image_name }}
    pull_policy: build
    restart: always
    user: "${HOST_UID:-1000}:${HOST_GID:-1000}"
    volumes:
      - .:/app
    env_file:
      - ./.env
    command: celery -A src beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    depends_on:
      - db
      - redis

volumes:
  redis_data:
```

`celery-worker` and `celery-beat` both use `{{ image_name }}` — the
same baked project image as `web`. One image, three processes,
differentiated only by `command`. This is the standard Celery
deployment pattern and requires no additional Dockerfile.

---

## Declaring the fragment in `pyproject.toml`

The fragment file must be included in the wheel's package data:

```toml
[tool.setuptools.package-data]
"phoxtail_booking" = ["deploy/**/*"]
```

Without this declaration the file is excluded from the wheel and the
discovery scan finds nothing.

---

## Developer workflow

Installing a new app that ships a fragment is a three-step sequence:

```bash
# 1. Drop the wheel
cp path/to/phoxtail_booking-0.1.0-py3-none-any.whl wheels/

# 2. Add the app to INSTALLED_APPS in src/settings/base.py
#    "phoxtail_booking",

# 3. Regenerate compose — services appear automatically
phoxtail docker create compose
```

The command outputs which services were discovered:

```
✓ Docker Compose file created: docker-compose.yaml
  App fragments merged: redis, celery-worker, celery-beat
```

Rebuild the Docker image and the new services are live:

```bash
docker compose up --build
```

Running `phoxtail docker create compose` again produces the same
result — the command regenerates the whole file from scratch on every
run. Hand-edits to `docker-compose.yaml` are overwritten; configuration
belongs in the fragment, not in the generated file.

---

## Celery scaffolding in new projects

Every project hatched with `phoxtail hatch` receives `src/celery.py`
and the corresponding import in `src/__init__.py`:

```python
# src/__init__.py
from .celery import app as celery_app  # noqa: F401
```

This is inert without a Celery-using app installed — no broker is
required, no workers are started, no compose services are added. When
`phoxtail-booking` (or any app that contributes a compose fragment
with workers) is installed, the scaffolding is already in place. No
manual `src/celery.py` setup is needed.

The `celery -A src worker` command used in fragments refers to this
module. `src` is the Django project package; `celery.py` inside it
exposes `app = Celery(...)`. The autodiscovery call on that object
finds tasks across all installed apps.

---

## Comparison with MCP entry points

MCP tool discovery uses `importlib.metadata.entry_points()` because
tools are discovered at Python runtime — packages must be installed on
`sys.path` for their code to be importable.

Compose fragment discovery reads wheel zip archives directly because
it runs on the host CLI where app packages are **not** installed (they
live inside the Docker image). The CLI cannot import `phoxtail_booking`;
it can open `phoxtail_booking-0.1.0-py3-none-any.whl` as a zip file
and read its contents by path convention.

This is why convention replaces entry points here. The trade-off is
explicit opt-in (entry points) vs. simplicity (path convention). Given
that the fragment path is the only thing inside `deploy/`, the
convention is unambiguous and the simplicity is worth it.
