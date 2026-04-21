# API Architecture

## Role

The API is the single HTTP surface for every Phoxtail app. It sits between the model layer (Django ORM) and every external consumer — the CLI, the MCP server, sync peers, and any future integration. Nothing reads or writes Phoxtail data over HTTP without going through this layer.

The API is a first-class citizen of the Phoxtail package, not an implementation detail of any single feature. It lives at `phoxtail/api/` alongside `phoxtail/cli/` and `phoxtail/mcp/`, at the same level of the package hierarchy.

## Package layout

```
phoxtail/api/
├── __init__.py              # NinjaAPI instance, router registration
├── urls.py                  # Django URL mounting (single path)
├── middleware.py             # Trailing-slash normalization, i18n guard
│
├── streams/                 # app: streams
│   ├── __init__.py          # package docstring
│   └── v1/
│       ├── __init__.py      # v1 aggregate router
│       ├── schemas.py       # Pydantic v2 schemas (the stable contract)
│       ├── _helpers.py      # internal utilities
│       ├── variants.py      # variant CRUD
│       ├── collections.py   # collection endpoints
│       ├── blocks.py        # block endpoints
│       └── context.py       # context assembly (POST /context/)
│
├── design/                  # app: design (future)
│   └── v1/
│       ├── __init__.py
│       ├── schemas.py
│       ├── palettes.py
│       ├── fonts.py
│       └── tokens.py
│
└── pages/                   # app: pages (future)
    └── v1/
        ├── __init__.py
        ├── schemas.py
        ├── sites.py
        ├── pages.py
        └── locales.py
```

### Why this shape

**One `NinjaAPI` instance.** Defined in `phoxtail/api/__init__.py`. Every app registers its router on this single instance. This gives us one OpenAPI schema, one Swagger UI, one authentication layer, and one middleware stack. Adding a new app is a two-line change: import the router, call `api.add_router()`.

**App-aligned sub-packages.** Each Django app (`streams`, `design`, `pages`, `booking`, ...) gets its own sub-package. This mirrors the Django app layout and keeps ownership clear — the person working on design tokens edits `api/design/`, not a shared file.

**Per-app versioning.** Within each app sub-package, API versions live in their own directories (`v1/`, `v2/`). This allows `streams` to ship a `v2` without forcing a version bump on `design`. URL-based versioning is the cheapest escape hatch when sync peers on different versions need to coexist.

**Pydantic v2 schemas as the contract.** Each version directory has a `schemas.py` that defines the request and response shapes. These schemas are the durable contract that CLI commands, MCP tools, and sync peers program against. Changes to schemas are version-gated; internal model changes that don't affect the schema are invisible to consumers.

## URL shape

The API is mounted at `/api/` in a hatched project's root `urls.py`. The full path includes the app name, the version, and the resource:

```
/api/streams/v1/variants
/api/streams/v1/variants/{identifier}
/api/streams/v1/collections
/api/streams/v1/collections/{identifier}
/api/streams/v1/blocks
/api/streams/v1/context/

/api/design/v1/palettes          (future)
/api/design/v1/fonts             (future)

/api/content/v1/sites              (future)
/api/content/v1/pages              (future)
```

The app name as the second segment means each app owns its own namespace. No collision, no coordination.

## Design conventions

These conventions apply to every endpoint across every app:

### Resource-oriented, not RPC

Every endpoint acts on a resource with standard HTTP verbs. Updates are `PUT /variants/{id}`, not `POST /variants/{id}/commit`. The only exception is context assembly (`POST /context/`), which is a computation, not a resource mutation — it reads from multiple models and returns a rendered document.

### Optimistic concurrency via ETag / If-Match

Every mutable resource response carries a weak ETag derived from a content hash. Write operations require the client to send the ETag back as an `If-Match` header. Mismatches return `412 Precondition Failed`. This protects against lost updates from any client (CLI, MCP, sync peer) and dogfoods the same primitive the sync protocol will use for fast-forward detection.

### Error shape

4xx and 5xx responses return `{"detail": "..."}`, aligned with RFC 7807 Problem Details. The field names are chosen so that hardening to the full RFC 7807 format (adding `type`, `status`, `instance`) is additive, not breaking.

### No session state

The API is stateless. Editing sessions, working copies, and conversation context are client-side concerns managed by the CLI or MCP layer. The API does not know or care whether a `PUT` came from a human typing a CLI command, an AI agent calling an MCP tool, or a remote project running a sync operation.

### Discovery

Django Ninja auto-generates an OpenAPI schema at `/api/openapi.json` and Swagger UI at `/api/docs`. This document is the machine-readable contract for every consumer.

## Middleware

`ApiTrailingSlashMiddleware` handles two problems specific to the Phoxtail URL landscape:

1. **Trailing-slash normalization.** Django's `APPEND_SLASH` issues redirects that drop request bodies on POST/PUT. The middleware rewrites `/api/foo` to `/api/foo/` in-place, without a redirect.
2. **i18n hijacking.** Wagtail's `i18n_patterns` catch-all sits at the bottom of `urls.py`. When Django Ninja returns a 404, `LocaleMiddleware` sees it, checks whether `/en/api/...` resolves (it does, via the Wagtail catch-all), and issues a redirect to an HTML error page. The middleware intercepts any 3xx response from an `/api/` path and replaces it with a JSON 404.

Both problems are scoped to `/api/` paths. Non-API routes keep Django's default behaviour.

## Relationship to other layers

```
MCP tools ──┐
CLI cmds  ──┤──► HTTP ──► API endpoints ──► Django ORM ──► Database
Sync peers ─┘
```

The API is the only way to read or write data over HTTP. The CLI, MCP, and sync layers are all API consumers. They do not import Django models or call ORM methods directly — they issue HTTP requests against the running application.

This boundary is load-bearing. It means:

- The API can be tested independently of any consumer.
- Consumers can be developed and tested against a mock HTTP server.
- The API server can evolve its ORM queries without breaking consumers, as long as the Pydantic schemas hold.
- Any new consumer (a web dashboard, a mobile app, a third-party integration) gets the same surface as the existing ones, with no special treatment.

## Adding a new app

Adding an API surface for a new Django app follows a consistent pattern:

1. Create `phoxtail/api/<app>/v1/` with `__init__.py`, `schemas.py`, and one module per resource.
2. Define Pydantic v2 schemas in `schemas.py`.
3. Write endpoint functions that query models and return schema instances.
4. Build the v1 aggregate router in `__init__.py`.
5. Import the router in `phoxtail/api/__init__.py` and call `api.add_router("/app/v1/", router, tags=["app/v1"])`.

The pattern is proven. `streams/v1/` is the reference implementation.

## What the API does not do

- **Authentication and authorization.** Currently unenforced. Phase 5 introduces bearer-token authentication for sync peers. Per-user authorization is a later concern.
- **Rate limiting.** Not needed while the only consumers are local CLI and MCP processes.
- **Caching headers beyond ETag.** The API runs on localhost against the same process. `Cache-Control` is a concern for the registry in Phase 6, not for the local API.
- **Pagination.** Current data volumes (tens to low hundreds of variants) don't require it. When they do, cursor-based pagination will be added as a backwards-compatible enhancement.

These are not oversights — they are deliberate scoping decisions that will be revisited when the use case demands them.
