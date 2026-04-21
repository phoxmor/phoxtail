# MCP Pages Domain

## What this is

The pages domain gives an AI agent the tools to read and write Wagtail page content — finding pages, inspecting their fields, editing scalar metadata, and manipulating StreamField body blocks. It is the content-authoring counterpart to the `studio` domain, which handles block variant templates.

Unlike `studio/`, which is a single cross-cutting domain owned by core, the pages domain is **split across core and apps**. Core ships everything that is generic to Wagtail (list, get, patch, publish, body editing, image and document lookup, dynamic page-type discovery). Apps that contribute their own `Page` subclasses (like `phoxtail.cms` for `SitePage`, or the optional `phoxtail.blog` for `BlogPostPage` / `BlogIndexPage`) *ship their own API router, MCP tools, and page-schema contributions* through `PhoxtailAppConfig`. A project that hatches without blog does not see blog endpoints, blog MCP tools, or blog page types — there is no dead surface.

## Why build this

Studio tools let an agent design and edit the *templates* (HTML/CSS/JS) that render blocks. But templates are empty until pages are filled with content. Without pages tools, an agent can design a `hero` block variant but cannot create a page that uses it, set its title, write its intro, or populate its StreamField body.

Pages tools close this gap. Together, studio and pages tools give an agent the full content-authoring surface: design the component, create the page, fill it with content, publish it.

The architectural split matters because Phoxtail ships as an **agentic application ecosystem**. Apps must be able to add new `Page` subclasses — with their own writable fields, their own FK-lookup endpoints, and their own MCP tools — without editing core. The contribution model described here is the public contract that makes this possible.

## Architecture principle: each app owns its namespace

Every Phoxtail app that exposes HTTP or MCP surface owns a stable,
app-scoped namespace derived from its Django `app_label`:

| Concern | Namespace |
|---|---|
| HTTP API | `/api/<label>/v1/` |
| MCP tools | `phoxtail_<label>_*` |
| Python package | `phoxtail.<label>.api.v1`, `phoxtail.<label>.mcp` |

`<label>` is the app's short label with the `phoxtail_` prefix stripped — `blog`, `booking`, `dashboard`, `cms`, `streams`, `pages`. This is the same label that Django uses for migrations and model references; it is already globally unique within a project, and it is the user-visible identifier the agent sees in tool names and URLs.

Two consequences:

1. **No cross-app URL nesting.** `phoxtail.blog`'s authors endpoint is `/api/blog/v1/authors/`, never `/api/content/v1/authors/`. The latter would say "pages domain owns authors, blog just implements them" — wrong, and a coupling we refuse.
2. **No cross-app MCP tool names.** Blog's author-listing tool is `phoxtail_blog_list_authors`, never `phoxtail_pages_list_authors`. The agent discovers which lookup tool to use for a given field by reading the `phoxtail://page-types` resource, which names the tool explicitly per FK.

The one exception — and it is unavoidable — is that the generic `GET /api/content/v1/pages/{id}/` endpoint must be able to serialize a `BlogPostPage` with its blog-specific fields. That cross-cut happens through an **internal** contribution registry (`page_schema_contributors`, below), never through URL routing.

## Extension points on `PhoxtailAppConfig`

Two class attributes on `PhoxtailAppConfig` let an app declare its HTTP
+ pages-domain surface. MCP tool discovery is intentionally **not** on
`PhoxtailAppConfig` — see [MCP registration](#mcp-registration) for why
it lives in `pyproject.toml` instead.

```python
from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailBlogConfig(PhoxtailAppConfig):
    name = "phoxtail.blog"
    label = "phoxtail_blog"

    # (1) One router per app, mounted automatically at /api/<short_label>/v1/
    api_version_router = "phoxtail.blog.api.v1.router"

    # (2) Dotted paths to zero-arg callables returning PageSchemaContribution
    # instances, consumed by phoxtail.api.pages.v1 to build the page-type
    # registry and the GET /pages/{id}/ response union.
    page_schema_contributors = [
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_post",
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_index",
    ]
```

Both fields are optional. Every existing `PhoxtailAppConfig` that sets
none of them continues to work unchanged.

| Field | Type | What it does |
|---|---|---|
| `api_version_router` | `str \| None` | Dotted path to a `ninja.Router`. Mounted by `phoxtail.api` at `/api/<short_label>/v1/` where `short_label = label.removeprefix("phoxtail_")`. The mount happens from `PhoxtailCoreConfig.ready()` — i.e. after Django's app registry is fully populated, so the contributed router module may freely import models. |
| `page_schema_contributors` | `list[str]` | Dotted paths to zero-arg callables that return `PageSchemaContribution`. Consumed by `phoxtail.api.pages.v1.contrib.collect_page_schemas()`. The registry powers (a) the `phoxtail://page-types` discovery resource, (b) the per-page-type fields surfaced in `GET /pages/{id}/`, and (c) the `PATCH` validation on scalar writes. |

The registry **must be explicit**, not introspective. Contributors name their writable fields and ship their own `serialize` and `apply_patch` callables. No `_meta.get_fields()` walking, no heuristic "is this field writable" logic. This is the single most important discipline in this design — it is the difference between a plugin system and a leaky abstraction.

## The `PageSchemaContribution` dataclass

```python
# phoxtail/api/content/v1/contrib.py
from dataclasses import dataclass
from typing import Callable
from wagtail.models import Page


@dataclass(frozen=True)
class PageSchemaContribution:
    model: type[Page]
    content_type: str               # "phoxtail_blog.blogpostpage"
    writable_fields: dict[str, dict] # {"intro": {"type": "str", "required": False}, ...}
    serialize: Callable[[Page], dict]
    apply_patch: Callable[[Page, dict], None]
    fk_lookups: dict[str, str] = None  # {"author": "phoxtail_blog_list_authors", ...}
```

- `writable_fields` is the JSON Schema-ish description returned by `phoxtail://page-types`. It tells the agent what it can PATCH and the shape of each value.
- `serialize(page)` returns a JSON-ready dict extending the base page fields — called from `GET /pages/{id}/`.
- `apply_patch(page, data)` mutates the page instance (doesn't save) — called from `PATCH /pages/{id}/`. The core endpoint calls `page.save_revision(user=request.auth)` after.
- `fk_lookups` maps a writable FK field to the MCP tool name the agent should call to resolve a human-readable name to the integer ID. The pages domain never needs to know that `phoxtail_blog_list_authors` exists; it just relays the string.

## Package layout

### Core pages domain — `phoxtail.api.pages.v1`

```
phoxtail/api/content/v1/
├── __init__.py          # aggregates sub-routers, mounted at /api/content/v1/
├── contrib.py           # PageSchemaContribution + collect_page_schemas()
├── pages.py             # list / get / patch / publish / unpublish
├── body.py              # body read + replace
├── media.py             # images, documents (always present — wagtailimages/docs)
├── page_types.py        # /page-types/ endpoint (dynamic via contrib)
├── schemas.py           # BasePageSchema + dynamic response union
├── _helpers.py          # ETag helpers, auth/perm helpers, serialization
└── tests/               # pytest suite — generic surface only
```

### Core pages MCP — `phoxtail.mcp.pages`

```
phoxtail/mcp/pages/
├── __init__.py
├── pages.py             # phoxtail_pages_list_pages, get_page, update_page, publish
├── body.py              # phoxtail_pages_get_body, replace_body
├── media.py             # phoxtail_pages_list_images, list_documents
└── resources.py         # phoxtail://page-types resource
```

### App contribution layout (example: `phoxtail.blog`)

```
phoxtail/blog/
├── apps.py                       # PhoxtailBlogConfig declares the three hooks
├── models.py                     # BlogPostPage, BlogIndexPage, BlogAuthor
├── api/
│   └── v1/
│       ├── __init__.py           # router aggregating all sub-routers
│       ├── authors.py            # GET /authors/  (router)
│       ├── page_schemas.py       # contribute_blog_post, contribute_blog_index
│       └── _helpers.py           # app-private serialization
└── mcp/
    ├── __init__.py               # imports submodules for tool registration
    └── authors.py                # @mcp_server.tool phoxtail_blog_list_authors
```

### Parallel: `phoxtail.cms` contributes `SitePage`

`SitePage` is always present (core CMS, hatched into every project). It ships its contribution exactly like blog:

```
phoxtail/cms/
├── apps.py              # PhoxtailCmsConfig.page_schema_contributors = [...]
├── models.py            # SitePage
└── api/
    └── v1/
        └── page_schemas.py    # contribute_site_page
```

`phoxtail.cms` has no FK lookups to expose and no own MCP tools today, so it omits `api_version_router` and `mcp_modules` and sets only `page_schema_contributors`.

## Auto-mounting — `phoxtail.api`

`phoxtail.api` declares the shared `NinjaAPI` instance and mounts the
fixed set of core routers (streams, pages) at module-import time.
Contributed `api_version_router`s are mounted later, from
`PhoxtailCoreConfig.ready()`:

```python
# phoxtail/api/__init__.py  (simplified)

api.add_router("/streams/v1/", streams_v1_router, tags=["streams/v1"])
api.add_router("/pages/v1/", pages_v1_router, tags=["pages/v1"])


def mount_contributed_routers() -> None:
    # Idempotent — invoked from PhoxtailCoreConfig.ready() so the walk
    # runs exactly once, after django.setup() has populated the app
    # registry. Importing `phoxtail.api` before setup() (e.g. from a
    # test that touches the package directly) no longer crashes — it
    # just defers the mount until ready() fires.
    for short, sub_router in collect_contributed_routers():
        api.add_router(f"/{short}/v1/", sub_router, tags=[f"{short}/v1"])
```

`collect_contributed_routers()` iterates `apps.get_app_configs()`,
filters to `PhoxtailAppConfig` instances with a non-null
`api_version_router`, imports the dotted path, and yields
`(short_label, router)` tuples. Collisions with a core short label
(`streams`, `pages`) raise `RuntimeError`.

**Short-label rule:** `short_label = config.label.removeprefix("phoxtail_")`. `phoxtail_blog` → `blog`. `phoxtail_booking_reservations` → `booking_reservations`. Any app whose label does not start with `phoxtail_` uses `config.label` verbatim.

## MCP registration

This is a design-load-bearing section — how optional apps ship their
own MCP tools is a question every future contributor will face. Read
it in full before adding a new app with MCP surface.

### The core question

*How does an installed-but-optional Django app contribute MCP tools to
the shared `phoxtail` server, without the core MCP package importing
each one by name?*

Three mechanisms were considered:

1. **`INSTALLED_APPS` + AppConfig attribute.** Each app declares
   `mcp_modules = [...]` on its `PhoxtailAppConfig`; the MCP server
   calls `django.apps.get_app_configs()` at startup and imports each
   declared module.
2. **Python entry points.** Each app distribution declares a
   `[project.entry-points."phoxtail.mcp_modules"]` table in its
   `pyproject.toml`; the MCP server uses `importlib.metadata` to
   discover and import them.
3. **Hardcoded imports.** Every optional app that ever ships MCP tools
   gets an explicit `from phoxtail.X.mcp import ...` inside core. Non
   starter — it welds core to the set of apps and defeats the purpose
   of the plugin system.

We use **#2 (entry points)** with one nuance — see below.

### Why entry points

Entry points are the canonical Python plugin-discovery mechanism.
`pytest`, `sphinx`, `flake8`, `setuptools` itself, and essentially
every major pluggable Python tool use them. The benefits that
specifically matter to Phoxtail:

- **No Django runtime required on the host.** `phoxtail mcp serve`
  runs from the user's tool venv (installed via `uv tool install`),
  not inside the Docker container. The host venv carries `phoxtail`
  and its CLI dependencies but *not* the project's full Django runtime
  (`django-environ`, `wagtail`, SQL drivers, …). Using
  `django.apps.get_app_configs()` for discovery would force a full
  `django.setup()` with settings that don't exist on the host — it
  fails hard. Entry points read pure package metadata; zero Django
  required.
- **Decoupled from `INSTALLED_APPS`.** An app can contribute tools
  purely by being *installed as a Python distribution* — no Django
  settings change required on the backend to make the host see the
  tool names. Useful for host-only tooling and for CI paths that
  exercise the MCP surface without a live backend.
- **Standard pattern, familiar to contributors.** Anyone who has
  written a pytest plugin already knows how it works. No Phoxtail-
  specific discovery protocol to learn.

### The bundled-app nuance

Phoxtail ships many optional Django apps inside one `phoxtail` Python
distribution (monorepo-style): `phoxtail.blog`, `phoxtail.booking`,
`phoxtail.cms`, and so on. Installing `phoxtail` installs all of them
as importable Python packages, whether or not the consuming project
adds them to `INSTALLED_APPS`.

That creates a mismatch with standard entry-point semantics: entry
points fire for every installed *distribution*, so `phoxtail_blog =
"phoxtail.blog.mcp"` fires whenever `phoxtail` is installed — even in
a project that never enabled blog. Without mitigation, the MCP catalog
shows `phoxtail_blog_list_authors`, the agent calls it, and it 404s
against a backend that never mounted `/api/blog/v1/authors/`.

**Fix: the app self-gates at import time.** Each contributed MCP
module checks the project manifest (`phoxtail.toml → [project].apps`)
— the host-side source of truth for "which phoxtail apps this project
uses" — before importing its submodules:

```python
# phoxtail/blog/mcp/__init__.py
from phoxtail.cli.utils.config import get_project_apps

if "phoxtail.blog" in get_project_apps():
    from phoxtail.blog.mcp import authors  # noqa: F401
```

We cannot gate on `django.apps.is_installed(...)` here — as noted
above, there is no Django runtime on the host when `phoxtail mcp
serve` runs. `phoxtail.toml` is the analogous manifest on the host and
is already loaded by every CLI command, so reading it here is free.

### When will this simplify?

Once an app graduates to its own distribution (e.g. `phoxtail-blog` on
PyPI), its entry point lives in *that* package's `pyproject.toml`. A
project that doesn't `pip install phoxtail-blog` never sees the entry
point, and the gate becomes redundant. Until then, the gate is the
right bridge between "one Python distribution" and "many optional
Django apps".

This same pattern is used by django-allauth's provider modules,
Wagtail's optional contrib packages, and DRF's optional renderers — a
single distribution with many feature flags gated on
`INSTALLED_APPS` (or, in our case, on a host-side manifest because
Django isn't available).

### Rules for future apps

When adding a new app `phoxtail.<name>` that contributes MCP tools:

1. Create a `phoxtail/<name>/mcp/` package. Its `__init__.py` reads
   `get_project_apps()` and gates submodule imports on
   `"phoxtail.<name>" in get_project_apps()`.
2. Each submodule registers its tools via `@mcp_server.tool(...)` and
   builds API paths against `/api/<short_label>/v1/...` using
   `phoxtail.mcp._http.bind_prefix`.
3. Add the entry point to the distributing package's `pyproject.toml`:

   ```toml
   [project.entry-points."phoxtail.mcp_modules"]
   phoxtail_<name> = "phoxtail.<name>.mcp"
   ```
4. **Do not** add an `mcp_modules` attribute to the AppConfig.
   `PhoxtailAppConfig` does not support one — discovery is entry-point
   driven, period.

### The current implementation

```python
# phoxtail/mcp/__init__.py  (simplified)
from importlib.metadata import entry_points


def _register_core_tools() -> None:
    from phoxtail.mcp.studio import (  # noqa: F401
        blocks, collections, context, prompts, resources, variants,
    )
    from phoxtail.mcp.pages import (  # noqa: F401
        pages, body, media, resources as pages_resources,
    )


def _register_contributed_tools() -> None:
    for ep in entry_points(group="phoxtail.mcp_modules"):
        importlib.import_module(ep.value)


def _register_tools() -> None:
    _register_core_tools()
    _register_contributed_tools()
```

Core tools are imported explicitly (they live in the same
distribution, always present, no gating needed). Contributed tools
come from entry points, and their self-gate keeps the catalog clean.

## HTTP client — `phoxtail.mcp._http`

The current `_http.py` hardcodes `API_PREFIX = "/api/streams/v1"`. That is removed. The shared `request()` helper takes a **full path** starting from `/api/`, and domain tool modules build their own prefixes:

```python
# phoxtail/mcp/_http.py
def request(method: str, path: str, *, ...) -> httpx.Response:
    # path is e.g. "/api/content/v1/pages/3/" or "/api/blog/v1/authors/"
    ...

def get_json(path: str, **params) -> dict: ...
```

Domain modules define their own prefix constant for readability:

```python
# phoxtail/mcp/pages/pages.py
API = "/api/pages/v1"

# phoxtail/blog/mcp/authors.py
API = "/api/blog/v1"
```

The existing studio modules are updated to pass `"/api/streams/v1/..."` explicitly. No silent breakage — the shared helper simply no longer injects a prefix.

## Authentication and permissions

Every request to the pages API is authenticated via the same PAT mechanism as the studio domain. The single `NinjaAPI` instance uses `PhoxtailTokenAuth`, which maps the Bearer token to a Django `User` instance and sets `request.auth = user`.

Write endpoints (`PATCH`, `PUT`, `POST /publish/`) check Wagtail page permissions on that user before proceeding:

```python
from wagtail.models import UserPagePermissionsProxy

perms = UserPagePermissionsProxy(request.auth)
if not perms.for_page(page).can_publish():
    raise HttpError(403, "User cannot publish this page.")
```

The PAT user therefore needs the Wagtail **"Publish" permission** on the relevant page tree. Editors restricted to "Add" or "Edit" only can read pages but will receive a 403 on any write. Grant the permission via the Wagtail admin (Settings → Groups → assign page publish permission) before running the MVP validation.

The `save_revision(user=...)` call passes `request.auth` directly, so the Wagtail revision history records the correct editor identity.

## Serialization: StreamField format

Verified against the running project. Wagtail's `stream_block.get_api_representation(value, context)` produces clean JSON for all Phoxtail schema block types:

```json
[
  {
    "type": "navbar",
    "value": { "variant": 15 },
    "id": "faa66889-be28-4a27-be58-7f83ed33d36a"
  },
  {
    "type": "video_banner",
    "value": {
      "file": 4,
      "thumbnail": null,
      "slides": [
        {
          "type": "slide",
          "value": { "supertitle": "Welcome", "title": "Home" },
          "id": "61b8f169-0000-0000-0000-000000000001"
        }
      ],
      "variant": 25
    },
    "id": "01fc1a5a-0000-0000-0000-000000000002"
  }
]
```

Key properties:

- FK references (images, documents, variants) are integers — not nested objects.
- Nested streams follow the same `{type, value, id}` structure recursively.
- Block UUIDs (`id`) are auto-generated on write and must be preserved on update.
- This format round-trips: the same JSON can be written back to the StreamField.

## FK resolution

FK fields (images, documents, variants) are represented as integers in the StreamField and in API responses. The agent needs to know the right integer before writing.

| FK target | Lookup | Who owns it |
|---|---|---|
| `BlockVariant` | `phoxtail_studio_list_variants` | core studio domain |
| `Image` | `phoxtail_pages_list_images` | core pages domain (wagtailimages is always present) |
| `Document` | `phoxtail_pages_list_documents` | core pages domain (wagtaildocs is always present) |
| `BlogAuthor` | `phoxtail_blog_list_authors` | `phoxtail.blog` (optional) |
| `<future FK in another app>` | `phoxtail_<app>_list_<thing>` | that app |

The agent finds the right lookup tool per field by reading `phoxtail://page-types`, which names the tool via `fk_lookups` in each contribution. No hardcoded knowledge of the blog app anywhere in core pages code.

## Page serialization

Page fields are exposed over the API following the Wagtail + Django Ninja pattern: a base schema carrying common Wagtail page fields, plus per-type fields injected via the `serialize` callable on each `PageSchemaContribution`. A discriminator field `content_type: str` (the app-label + model-name string, e.g. `"phoxtail_cms.sitepage"`) lets clients dispatch on the concrete type.

### Concrete `GET /api/content/v1/pages/3/` response

```json
{
  "id": 3,
  "title": "Home",
  "slug": "home",
  "live": true,
  "first_published_at": "2026-04-19T22:59:01.639000Z",
  "last_published_at": "2026-04-20T15:14:37.930565Z",
  "seo_title": "",
  "search_description": "",
  "content_type": "phoxtail_cms.sitepage",
  "url": "http://localhost/en/",
  "body": [
    {
      "type": "navbar",
      "value": { "variant": 15 },
      "id": "faa66889-be28-4a27-be58-7f83ed33d36a"
    }
  ]
}
```

`url` is `null` for pages that have never been published (`live=false` and no `first_published_at`).

### Common fields (all page types)

| Field | Type | Writable |
|---|---|---|
| `id` | int | no |
| `title` | str | yes |
| `slug` | str | yes |
| `live` | bool | no (use publish/unpublish) |
| `first_published_at` | datetime \| null | no |
| `last_published_at` | datetime \| null | no |
| `seo_title` | str | yes |
| `search_description` | str | yes |
| `content_type` | str | no |
| `url` | str \| null | no (null if never published) |

Every core field above is serialized + patched by the generic pages endpoint without any contribution. All remaining per-type fields come from the contributor. Examples follow.

### `SitePage` contribution (from `phoxtail.cms`)

```python
{
  "body": list[StreamBlock]   # writable via body tools
}
```

### `BlogIndexPage` contribution (from `phoxtail.blog`)

```python
{
  "posts_per_page": int,      # writable
  "body": list[StreamBlock]   # writable via body tools
}
```

### `BlogPostPage` contribution (from `phoxtail.blog`)

```python
{
  "intro": str,                                  # writable
  "read_mins": int,                              # writable
  "author": int,          # FK → BlogAuthor; fk_lookups["author"] = "phoxtail_blog_list_authors"
  "preview_image": int,   # FK → Image;       fk_lookups["preview_image"] = "phoxtail_pages_list_images"
  "tags": list[str],                             # writable
  "hide_dates": bool,                            # writable
  "first_published_at_override": datetime|None,  # writable
  "last_published_at_override": datetime|None,   # writable
  "body": list[StreamBlock]                      # writable via body tools
}
```

**Tags policy**: tags are matched case-insensitively against existing Wagtail `Tag` objects; unknown tag strings are created automatically on write. There is no allowlist — the API does not reject new tag names.

## Publishing semantics

Wagtail pages have a revision + publication model. Every write operation creates a draft revision and does not immediately publish:

```python
revision = page.save_revision(user=request.auth)
# later, to go live:
revision.publish()
```

This means:

- `PATCH /api/content/v1/pages/{id}/` — updates scalar fields (core + contributed), saves a draft revision.
- `PUT /api/content/v1/pages/{id}/body/` — replaces the body, saves a draft revision.
- `POST /api/content/v1/pages/{id}/publish/` — publishes the latest draft.
- `POST /api/content/v1/pages/{id}/unpublish/` — takes the page offline.

An agent workflow therefore ends with an explicit publish step. The agent cannot accidentally publish — it must call the publish tool.

## Core MCP tool surface (pages domain)

### Pages tools

| Tool | Description |
|---|---|
| `phoxtail_pages_list_pages` | List pages, filtered by `type`, `parent`, `live` |
| `phoxtail_pages_get_page` | Full detail of a single page (core + contributed fields + body) with ETag |
| `phoxtail_pages_update_page` | Patch scalar fields; creates a draft revision |
| `phoxtail_pages_publish` | Publish the latest draft revision |
| `phoxtail_pages_unpublish` | Take a page offline (post-MVP) |
| `phoxtail_pages_create_page` | Create a new draft page under a parent (post-MVP) |

### Body editing tools

The MVP exposes only full-body replacement. Surgical per-block tools are added in the next phase.

| Tool | Description | Phase |
|---|---|---|
| `phoxtail_pages_get_body` | Current body as `[{type, value, id}]` with ETag | MVP |
| `phoxtail_pages_replace_body` | Full body replacement (ETag required) | MVP |
| `phoxtail_pages_list_body_blocks` | List blocks with type, id, short summary | post-MVP |
| `phoxtail_pages_get_body_block` | Full value of a single block by id, with ETag | post-MVP |
| `phoxtail_pages_update_body_block` | Replace a single block's value by id (ETag required) | post-MVP |
| `phoxtail_pages_insert_body_block` | Insert a new block after a given block id (or at start) | post-MVP |
| `phoxtail_pages_delete_body_block` | Remove a block by id (ETag required) | post-MVP |

### Media lookup tools

| Tool | Description |
|---|---|
| `phoxtail_pages_list_images` | Search images by title; returns `[{id, title, file_url}]` |
| `phoxtail_pages_list_documents` | Search documents by title; returns `[{id, title, file_url}]` |

### Discovery resource

```
phoxtail://page-types
```

An MCP resource enumerating every page type the registry knows about. Response shape (JSON):

```json
{
  "phoxtail_cms.sitepage": {
    "writable_fields": { ... },
    "fk_lookups": {}
  },
  "phoxtail_blog.blogpostpage": {
    "writable_fields": { ... },
    "fk_lookups": {
      "author": "phoxtail_blog_list_authors",
      "preview_image": "phoxtail_pages_list_images"
    }
  }
}
```

In a project with no blog installed, the `phoxtail_blog.*` keys simply are not present. The resource does **not** duplicate block value schemas: to understand the shape of a block's `value` object, the agent calls `phoxtail://schema-reference` (the existing studio resource, backed by `/api/streams/v1/schema-catalog/`). The two resources compose: `page-types` says which block types are allowed; `schema-reference` says what their fields look like.

## Contributed MCP tools (example: `phoxtail.blog`)

| Tool | Description | Ships with |
|---|---|---|
| `phoxtail_blog_list_authors` | Search blog authors by name/email; returns `[{id, title}]` | `phoxtail.blog` |

Future apps contribute their own tools in their own `phoxtail_<label>_*` namespace. Core pages code never references them by name — only via the `fk_lookups` string the contributor emits.

## Concurrency control

The same ETag pattern used by studio tools applies here. There is one ETag per page — it covers the entire page state including the body. There is no separate per-block ETag (the body is stored as a single JSON blob in the database; per-block ETags would race).

- `GET /api/content/v1/pages/{id}/` returns an `ETag` header derived from the latest revision timestamp.
- `GET /api/content/v1/pages/{id}/body/` returns the same page-level ETag.
- `PATCH` (scalar fields), `PUT` (body replacement), and `POST /publish/` all require `If-Match: <etag>`.
- `412 Precondition Failed` — the page has changed since the last read; agent must re-fetch.
- `428 Precondition Required` — `If-Match` header is missing.

After a successful write, the response includes the new ETag. The agent can continue making writes with the updated ETag without re-fetching.

## Error taxonomy

All error responses from the pages API use the existing shared `Error` schema:

```json
{ "detail": "<human-readable message>", "title": "<optional short code>" }
```

| Status | Meaning |
|---|---|
| 400 | Request body failed schema validation |
| 403 | User lacks Wagtail publish/edit permission |
| 404 | Page, block, or resource does not exist |
| 409 | Concurrent write created a newer revision |
| 412 | `If-Match` ETag does not match current state |
| 428 | `If-Match` header missing on a write request |

MCP tool wrappers catch non-2xx responses and return structured error JSON to the agent so the agent can reason about the failure rather than receiving a raw HTTP exception.

## Testing

```
phoxtail/api/content/v1/tests/
├── conftest.py          # fixtures: test client, auth token, page tree, contrib helpers
├── test_pages.py        # list, get, patch, publish (generic only)
├── test_body.py         # body get + replace
├── test_media.py        # image, document list endpoints
├── test_page_types.py   # contrib registry + /page-types/ endpoint
└── test_contrib.py      # PageSchemaContribution wiring, missing-app behaviour

phoxtail/blog/api/v1/tests/
├── conftest.py
├── test_authors.py      # GET /api/blog/v1/authors/
└── test_page_schemas.py # BlogPostPage / BlogIndexPage contribution + PATCH round-trip
```

Follow the same pattern as `phoxtail/api/streams/v1/tests/`: use `django_db` + Wagtail's `Page.add_child()` to build a minimal page tree, create a PAT, and test each endpoint via the Ninja test client.

Core pages tests **must not import `phoxtail.blog`**. The blog contribution tests live in the blog app alongside its router.

The MVP is not validated until the tests pass against a real in-process database — no mocking of the ORM.

## MVP: validating the path

The MVP covers a single end-to-end authoring workflow on `BlogPostPage`. It is the smallest thing that proves the whole chain — core pages API → blog contribution → MCP → agent fills a real page with real content.

### Prerequisite: create a draft page

The live project starts with zero `BlogPostPage` instances. Before running the MVP checklist, create one manually in the Wagtail admin:

1. Go to the Wagtail Pages tree.
2. Add a child under the Blog Index page, choosing `BlogPostPage`.
3. Save it as a draft (do not publish).
4. Note its numeric ID from the URL.

Page creation via the API is post-MVP (see implementation order).

### MVP scope

**Core pages API endpoints:**

- `GET /api/content/v1/pages/`  (with `?type=phoxtail_blog.BlogPostPage`)
- `GET /api/content/v1/pages/{id}/`  (with ETag)
- `PATCH /api/content/v1/pages/{id}/`  (scalar fields, core + contributed)
- `GET /api/content/v1/pages/{id}/body/`  (with ETag)
- `PUT /api/content/v1/pages/{id}/body/`  (full replacement)
- `POST /api/content/v1/pages/{id}/publish/`
- `GET /api/content/v1/page-types/`
- `GET /api/content/v1/media/images/`
- `GET /api/content/v1/media/documents/`

**Contributed endpoints (blog):**

- `GET /api/blog/v1/authors/`

**Core pages MCP tools:**

- `phoxtail_pages_list_pages`
- `phoxtail_pages_get_page`
- `phoxtail_pages_update_page`
- `phoxtail_pages_get_body`
- `phoxtail_pages_replace_body`
- `phoxtail_pages_publish`
- `phoxtail_pages_list_images`
- `phoxtail_pages_list_documents`

**Contributed MCP tools (blog):**

- `phoxtail_blog_list_authors`

**Discovery:**

- `phoxtail://page-types` — enumerates `SitePage`, `BlogIndexPage`, `BlogPostPage` when blog is installed; only `SitePage` when it isn't.

**Deliberately deferred from MVP:**

- Surgical block editing (list/get/insert/update/delete individual blocks)
- Page creation under a parent
- Unpublish
- FK contributions for content types beyond blog

### MVP validation checklist

The MVP is viable if an agent can complete all of the following in a single conversation (starting from the prerequisite draft page):

1. Call `phoxtail://page-types` and read the `BlogPostPage` field schema.
2. Call `phoxtail://schema-reference` to read the shape of the block types that will be used in the body.
3. Call `phoxtail_pages_list_pages` with `?type=phoxtail_blog.BlogPostPage` and find the draft page by title.
4. Call `phoxtail_pages_get_page` and read its current scalar fields + body. Record the ETag.
5. Call `phoxtail_blog_list_authors` to find the author FK integer.
6. Call `phoxtail_pages_update_page` to set `title`, `intro`, `author`, `read_mins`, `tags` — verify a draft revision is created and a new ETag is returned.
7. Call `phoxtail_studio_list_variants` to find variant IDs for the blocks to use in the body.
8. Call `phoxtail_pages_replace_body` with a new body containing at least two blocks of different types — verify the body saves as a draft and a new ETag is returned.
9. Call `phoxtail_pages_publish` — verify the page goes live.
10. Re-fetch with `phoxtail_pages_get_page` — verify `live=true`, `url` is non-null, and the updated fields appear.

If steps 1–10 complete without the agent needing to read source code, guess field names, or manually construct Wagtail internals, the path is validated and surgical block editing tools are worth building.

### What the MVP does not validate

- Whether the agent can write *good* content (a prompting problem, not an API problem).
- Whether block-level surgical editing is ergonomic (validated in the next phase).
- Whether image FK lookups are smooth in practice (media tools are in MVP but not exercised heavily).

## Relationship to studio tools

Pages tools and studio tools are complementary and are often used together in sequence:

```
1. phoxtail_studio_list_blocks          → discover which block types exist
2. phoxtail_studio_list_variants        → find the variant IDs to reference in blocks
3. phoxtail://schema-reference          → understand block value shapes
4. phoxtail://page-types                → know what fields each page type has + which FK tool to call
5. phoxtail_blog_list_authors           → resolve author FK (contributed by blog)
6. phoxtail_pages_get_page              → read current state + ETag
7. phoxtail_pages_update_page           → set scalar fields (core + contributed)
8. phoxtail_pages_replace_body          → set body blocks
9. phoxtail_pages_publish               → go live
```

## Implementation order

1. Extend `PhoxtailAppConfig` with `api_version_router`, `mcp_modules`, `page_schema_contributors`.
2. Build `phoxtail/api/content/v1/contrib.py` — `PageSchemaContribution`, `collect_page_schemas()`.
3. Teach `phoxtail/api/__init__.py` to auto-mount contributed `api_version_router`s at `/api/<short_label>/v1/`.
4. Build core generic pages endpoints: list/get + page-types + media (read-only, no risk).
5. Wire `phoxtail.cms` contribution for `SitePage` (the one that is always present).
6. Add scalar `PATCH` + body `GET` + body `PUT` to core; validate with the `SitePage` contribution.
7. Add `POST /publish/`.
8. Core MCP layer (`phoxtail.mcp.pages` + entry-point discovery for contributed `mcp_modules`).
9. Migrate `phoxtail.blog` to `PhoxtailAppConfig`; ship `phoxtail/blog/api/v1/` (authors + page schemas) and `phoxtail/blog/mcp/` (authors tool).
10. Tests — core first, then blog.
11. MVP validation checklist.
12. Surgical block tools (after MVP passes).
13. Page creation under a parent + unpublish.
14. `BlogIndexPage` refinements and any additional contributed apps.
