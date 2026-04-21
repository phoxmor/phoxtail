# App Contribution Model

Phoxtail is an **agentic application ecosystem**: every app ships not
only its Django models and templates but also the HTTP endpoints and
MCP tools that let AI agents read and write its data. The mechanism
that wires these surfaces together — without central registries knowing
anything about individual apps — is the app contribution model.

This document describes the model end-to-end: the ownership principle,
the short-label convention, the two discovery runtimes and why they
differ, the three contribution points, and how everything fits together
for a complete optional app like `phoxtail.blog`.

---

## The core principle: vertical-slice ownership

Each Phoxtail app owns its entire vertical slice:

```
phoxtail/<app>/
├── models.py            # Django/Wagtail models
├── apps.py              # PhoxtailAppConfig with contribution declarations
├── api/
│   └── v1/              # Ninja router + schemas + helpers
├── mcp/                 # MCP tool modules
└── templates/ ...
```

The central packages (`phoxtail/api/`, `phoxtail/mcp/`) are **mounting
points**, not owners. They discover and mount what each app declares;
they contain no domain knowledge themselves. A project that omits
`phoxtail.blog` gets no blog endpoints, no blog MCP tools, no blog page
types — no dead surface anywhere.

This is distinct from the older pattern (pre-contribution-model) where
`phoxtail/api/streams/` and `phoxtail/mcp/studio/` lived centrally.
Those are intermediate deviations; see
[Current deviations from the target state](#current-deviations-from-the-target-state).

---

## The short-label convention

Every Phoxtail app has a Django `label` of the form `phoxtail_<name>`.
The contribution model strips the `phoxtail_` prefix to derive a
**short label** that governs both the HTTP URL and the MCP tool prefix:

| App `label` | Short label | HTTP prefix | MCP tool prefix |
|---|---|---|---|
| `phoxtail_blog` | `blog` | `/api/blog/v1/` | `phoxtail_blog_*` |
| `phoxtail_cms` | `cms` | `/api/cms/v1/` | `phoxtail_cms_*` |
| `phoxtail_pages` | `pages` | `/api/pages/v1/` | `phoxtail_pages_*` |
| `phoxtail_streams` | `streams` | `/api/streams/v1/` | `phoxtail_studio_*` |

The short label is stable. Moving code from `phoxtail/api/<app>/` into
`phoxtail/<app>/api/` changes the import path, never the URL or tool
name. External consumers are insulated from internal restructuring.

Two invariants enforced at startup:

1. **No core-label collision.** `phoxtail/api/__init__.py` maintains
   `_CORE_SHORT_LABELS` to prevent an optional app from shadowing a core
   domain's URL. This guard is temporary scaffolding; it disappears once
   every core domain migrates to the per-app layout.
2. **No duplicate short labels.** Two apps cannot both claim
   `/api/foo/v1/`.

---

## The two discovery runtimes

There are two distinct runtimes where phoxtail tools are discovered,
and they are genuinely different — not an inconsistency to paper over.

### Runtime 1 — the backend (Django bootstrapped)

The API server and the Django admin run inside the project's Docker
container with a fully bootstrapped Django stack. Discovery here uses
Django's app registry, which is guaranteed to be populated by the time
`AppConfig.ready()` fires.

**Contribution mechanism:** class attributes on `PhoxtailAppConfig`.
`PhoxtailCoreConfig.ready()` calls `mount_contributed_routers()`, which
walks `apps.get_app_configs()`, finds every `PhoxtailAppConfig` with
`api_version_router` set, and mounts the router onto the shared
`NinjaAPI` instance.

### Runtime 2 — the host (no Django)

`phoxtail mcp serve` runs on the **developer's host machine** as a
pure HTTP client that talks to the dockerized backend. There is no
Django runtime on the host — no models, no `apps.is_installed()`, no
app registry.

**Contribution mechanism:** the `phoxtail.mcp_modules` Python
entry-point group declared in each app's `pyproject.toml`. The MCP
server calls `importlib.metadata.entry_points(group="phoxtail.mcp_modules")`
at startup, then imports each declared module. The entry-point fires
whenever the `phoxtail` package is installed, so optional app modules
that gate on a project-manifest check (see below) are always imported
but may be no-ops for projects that don't use the app.

**The project-manifest gate.** Because the entry-point fires for every
installed package — not only for projects that actually use an app —
optional MCP modules gate their tool registration on the project's
`phoxtail.toml → [project].apps` list:

```python
# phoxtail/blog/mcp/__init__.py
from phoxtail.cli.utils.config import get_project_apps

if "phoxtail.blog" in get_project_apps():
    from phoxtail.blog.mcp import authors  # noqa: F401
```

`get_project_apps()` reads `phoxtail.toml` — the host-side manifest
that answers "which apps does this project use?" without touching
Django. Tools are only registered when the backend would actually have
the corresponding endpoints; a missing app never leaks a dead tool into
the agent's tool list.

!!! warning "Do not replace this gate with `apps.is_installed()`"
    `django.apps.apps.is_installed` does not exist on the host.
    Replacing `get_project_apps()` with it breaks `phoxtail mcp serve`.
    This is the most common wrong refactor — resist the temptation.

### Summary

| Concern | Discovery mechanism | Runtime |
|---|---|---|
| API routers | `PhoxtailAppConfig.api_version_router` → `ready()` | Backend |
| Page-schema contributions | `PhoxtailAppConfig.page_schema_contributors` | Backend |
| MCP tool modules | `phoxtail.mcp_modules` entry point in `pyproject.toml` | Host |
| MCP per-app gate | `"<app>" in get_project_apps()` reading `phoxtail.toml` | Host |

---

## The three contribution points

### 1. `api_version_router` — HTTP surface

```python
class PhoxtailBlogConfig(PhoxtailAppConfig):
    name = "phoxtail.blog"
    label = "phoxtail_blog"
    api_version_router = "phoxtail.blog.api.v1.router"
```

A dotted path to a `ninja.Router`. `mount_contributed_routers()`
imports it and mounts it at `/api/<short_label>/v1/`. The mount is
idempotent — a module-level flag prevents double-mounting if `ready()`
somehow fires twice.

The router lives inside the app's own package (`phoxtail/blog/api/v1/`),
alongside its schemas and helpers. Core contributes nothing to it.

### 2. `page_schema_contributors` — per-Page-type fields

```python
class PhoxtailBlogConfig(PhoxtailAppConfig):
    page_schema_contributors = [
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_post",
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_index",
    ]
```

A list of dotted paths to zero-arg callables, each returning a
`PageSchemaContribution`. Consumed by `phoxtail.api.pages.v1.contrib`
to build the page-type registry, which powers:

- `GET /api/pages/v1/page-types/` — discovery resource for agents.
- `GET /api/pages/v1/pages/{id}/` — per-type extra fields merged into
  the generic page response.
- `PATCH /api/pages/v1/pages/{id}/` — per-type scalar writes applied
  after common Wagtail fields.

See [Page Schema Contributions](page-schema-contributions.md) for the
full protocol.

### 3. `phoxtail.mcp_modules` entry point — MCP surface

```toml
# pyproject.toml (the app's distributing package)
[project.entry-points."phoxtail.mcp_modules"]
blog = "phoxtail.blog.mcp"
```

Declares a module to be imported at MCP server startup. The module's
top-level code registers tools on `phoxtail.mcp.mcp_server` using
`@mcp_server.tool(...)`. The entry-point name (e.g. `blog`) is
cosmetic; the value is the dotted module path.

When the app ships as part of the `phoxtail` monorepo package, its
entry point is declared alongside every other app's entry point in the
root `pyproject.toml`. When the app ships as an independent package,
it declares its own entry point and the host discovers it via
`importlib.metadata`.

---

## End-to-end example: `phoxtail.blog`

The blog app is the reference implementation of every contribution
point. Tracing it end-to-end grounds the abstract model in real code.

### Package layout

```
phoxtail/blog/
├── models.py                          # BlogAuthor, BlogIndexPage, BlogPostPage
├── apps.py                            # PhoxtailBlogConfig
├── api/
│   └── v1/
│       ├── __init__.py
│       ├── router.py                  # ninja.Router (mounted at /api/blog/v1/)
│       ├── authors.py                 # GET /authors/
│       └── page_schemas.py            # contribute_blog_post, contribute_blog_index
└── mcp/
    ├── __init__.py                    # phoxtail.toml gate
    └── authors.py                     # phoxtail_blog_list_authors tool
```

### `apps.py` — the single wiring declaration

```python
from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailBlogConfig(PhoxtailAppConfig):
    name = "phoxtail.blog"
    label = "phoxtail_blog"

    api_version_router = "phoxtail.blog.api.v1.router"

    page_schema_contributors = [
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_post",
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_index",
    ]
```

`pyproject.toml` declares the MCP entry point separately (host-side):

```toml
[project.entry-points."phoxtail.mcp_modules"]
blog = "phoxtail.blog.mcp"
```

### What wires automatically on `django.setup()`

1. `PhoxtailCoreConfig.ready()` → `mount_contributed_routers()` →
   `phoxtail.blog.api.v1.router` mounted at `/api/blog/v1/`.
2. `collect_page_schemas()` (called lazily on first request to
   `/api/pages/v1/page-types/` or `GET /pages/{id}/`) → imports
   `contribute_blog_post` and `contribute_blog_index`, adds them to the
   page-type registry.

### What registers at MCP server startup

1. `_register_contributed_tools()` → imports `phoxtail.blog.mcp`.
2. `phoxtail/blog/mcp/__init__.py` → checks `phoxtail.toml`; if blog is
   listed, imports `phoxtail.blog.mcp.authors`.
3. `authors.py` → `@mcp_server.tool(name="phoxtail_blog_list_authors",
   ...)` registers the tool.

An agent sees `phoxtail_blog_list_authors` in its tool list only for
projects that list `phoxtail.blog` in `phoxtail.toml`.

### The agent-visible namespace

| Surface | Address |
|---|---|
| Author list | `GET /api/blog/v1/authors/` |
| Blog post fields (via page-type registry) | `phoxtail://page-types` → `phoxtail_blog.blogpostpage` |
| Author MCP lookup | `phoxtail_blog_list_authors` |
| Page read/write | `phoxtail_pages_get_page`, `phoxtail_pages_update_page`, … (core) |

---

## Adding a new app from scratch

A developer creating a new optional app `phoxtail.recipes` follows this
checklist:

1. **`apps.py`** — subclass `PhoxtailAppConfig`, set `label =
   "phoxtail_recipes"`. Declare `api_version_router` and/or
   `page_schema_contributors` as needed.
2. **`phoxtail/recipes/api/v1/`** — write a `ninja.Router` and any
   endpoint modules. Schemas in `schemas.py`. No imports from
   `phoxtail.api`.
3. **`phoxtail/recipes/mcp/`** — write tool modules; register on
   `phoxtail.mcp.mcp_server`. Gate `__init__.py` on
   `get_project_apps()`.
4. **`pyproject.toml`** — add the `phoxtail.mcp_modules` entry point.
5. **Page schemas** (if the app ships `Page` subclasses) — write
   `contribute_*` factories and declare them in `page_schema_contributors`.
   See [Page Schema Contributions](page-schema-contributions.md).

Core needs zero changes.

---

## Current deviations from the target state

The following packages exist at the central level rather than inside
their owning apps. They are **intentional intermediate steps** — all
wiring addresses are already stable and will not change when the
migration happens.

| Current location | Target location | Status |
|---|---|---|
| `phoxtail/api/streams/v1/` | `phoxtail/streams/api/v1/` | Not yet migrated |
| `phoxtail/mcp/studio/` | `phoxtail/streams/mcp/studio/` | Not yet migrated |
| `phoxtail/api/pages/v1/` | `phoxtail/pages/api/v1/` | Not yet migrated |
| `phoxtail/mcp/pages/` | `phoxtail/pages/mcp/` | Not yet migrated |

The `_CORE_SHORT_LABELS = frozenset({"streams", "pages"})` guard in
`phoxtail/api/__init__.py` exists solely to protect these interim
paths. It is removed as part of the migration.

### The `phoxtail.pages` question

The generic Wagtail page surface (list/get/patch/publish, media lookup,
page-type discovery, `PageSchemaContribution` registry) is a cross-app
concern: it must work for projects that use `phoxtail.cms`, projects
that use `phoxtail.blog`, projects that use neither, and projects that
ship their own custom `Page` subclasses. It cannot live in `phoxtail.cms`
(which is an opinionated `SitePage` offering, optional) or in
`phoxtail.core` (which is the wiring mechanism, always present).

The target is a dedicated `phoxtail.pages` Django app — one app, one
job, following the same rules as every other app. This is not yet
decided and not yet implemented. The pattern doc names it as the most
likely destination; the final decision will be recorded here when made.

### Why the migration is low-risk

URLs are constructed from short labels derived from `app_label`, not
from the Python import path. Moving `phoxtail/api/pages/v1/` into
`phoxtail/pages/api/v1/` changes the import but leaves
`/api/pages/v1/...` identical. The same applies to MCP tool names,
which are literal strings in `@mcp_server.tool(name=...)` decorators.

### Note on existing architecture docs

`phoxtail/docs/docs/api/architecture.md` and
`phoxtail/docs/docs/mcp/architecture.md` predate the contribution
model and are partially stale — the API doc lists pages as "future" and
the MCP doc describes domain-aligned (not app-aligned) sub-packages as
the intended structure. Both will be updated when the migration lands.
Until then, this document and
[Page Schema Contributions](page-schema-contributions.md) are the
authoritative reference for the contribution model.
