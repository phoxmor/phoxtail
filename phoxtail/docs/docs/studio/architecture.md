# Architecture

## Core insight: a variant is data

The `BlockVariant` model in `streams/models.py` carries three `TextField` columns — `html`, `css`, `javascript` — alongside metadata (name, identifier, block, collection, description, preview image). That row _is_ the variant. Everything else in the system is a view, a renderer, or a transport for that row.

Every design decision below follows from this.

## The database is the source of truth

Historically, default variants have shipped as files under `streams/management/data/blocks/<block>/variants/<collection>/<variant>/{template.html,style.css,script.js}` and have been seeded into the database during project hatch. Under Phoxtail Studio, **those files are demoted to one-time seed fixtures**. After the first `populate_streams`, the database is the only place that holds the live state of a variant.

This matters because the [sync protocol](sync.md) exchanges rows, not files. If two projects both ran `populate_streams` from the same fixture and then diverged independently, the fixture is no longer a meaningful reference point — it is only a common ancestor. The row is the working copy, the registry entry is the canonical version, and the seed file is a historical curiosity.

Consequences:

- Over time, Phoxtail itself ships fewer hard-coded variant files. A minimal bootstrap collection remains so that a freshly hatched project has something to render; everything else is pulled from a registry the first time a project needs it.
- Editing a variant is a database UPDATE, not a file write. Git is not the versioning mechanism — the sync protocol is.
- A designer working on a variant does not need to touch the Phoxtail source tree. They operate entirely inside their project's database, through the CLI.

## Four layers

```
┌──────────────────────────────────────────────────┐
│ 4. Agent layer                                   │
│    MCP server, consumed by Claude Code or any    │
│    MCP-aware client                              │
├──────────────────────────────────────────────────┤
│ 3. CLI layer                                     │
│    phoxtail studio <verb>                        │
│    (Typer sub-app, Rich formatting, httpx)       │
├──────────────────────────────────────────────────┤
│ 2. API layer                                     │
│    Django Ninja endpoints on the running app     │
│    /api/streams/v1/ (Pydantic v2 schemas, JSON)  │
├──────────────────────────────────────────────────┤
│ 1. Model layer                                   │
│    BlockVariant, VariantCollection, Block         │
└──────────────────────────────────────────────────┘
```

**Layer 1 — Models.** `Block`, `BlockVariant`, `VariantCollection`, and `SharedBlock` in `streams/models.py`. The `BlockSystemPrompt` model has been removed — context is now assembled from a static Jinja2 template shipped with phoxtail. New models arrive with the [sync protocol](sync.md) to track identity, version, and provenance across projects.

**Layer 2 — API.** A Django Ninja API mounted at `/api/streams/v1/` on the running Phoxtail app. The API layer lives in a top-level `phoxtail/api/` package that mirrors the app layout (`phoxtail/api/streams/`, `phoxtail/api/design/`, ...) so that every app's endpoints have one obvious home and each app can ship its own `v2` independently. Endpoints are thin — they query models, serialize through Pydantic v2 schemas, and return JSON. The Pydantic schemas are the stable contract for agents and scripts. The API runs inside the same Django process that serves Wagtail pages, so there is no container startup cost — responses are near-instant. This layer also provides the HTTP foundation that the [sync protocol](sync.md) builds on in later phases: projects exchange data over the same HTTP surface that the CLI consumes locally.

**Layer 3 — CLI.** A Typer sub-app at `phoxtail/cli/studio/`, registered in `phoxtail/__main__.py`, provides the `phoxtail studio <verb>` surface. Each CLI command calls the corresponding API endpoint via `httpx` and presents the result with Rich formatting. The CLI package follows the same structure as `phoxtail/cli/server/` — a self-contained package with its own client, formatters, and session management, with one module per verb.

**Layer 4 — Agents.** An MCP (Model Context Protocol) server exposes a subset of the CLI verbs as MCP tools. A designer running `claude` in a Phoxtail project gets Phoxtail-aware tools in their conversation without custom prompt engineering. The MCP server is a thin wrapper over the same API endpoints; it does not introduce its own logic, and it cannot do anything the CLI cannot.

Each layer depends only on the layer below it. Any layer can be replaced independently — a future web UI, for instance, would sit alongside layer 3 and also consume layer 2, without requiring changes to layers 1 or 2.

## API design conventions

The Studio API is consumed by three kinds of clients: the local CLI, the MCP server, and (from Phase 5 onwards) remote Phoxtail projects acting as sync peers. The last of those is the reason the API has to behave like a durable contract, not an internal implementation detail.

- **Base path `/api/streams/v1/`.** The API lives under `/api/` alongside any future Phoxtail API surfaces. The app name (`streams`) is the second segment so that each app (`streams`, `design`, `booking`, ...) owns its own namespace and its own version cadence. The version is in the URL because URL-based versioning is the cheapest escape hatch when Phase 5 sync clients on different versions need to coexist.
- **Resource-oriented, not RPC.** Every endpoint acts on a resource with standard HTTP verbs. Updates are `PUT /variants/{id}`, not `POST /variants/{id}/commit`. Context assembly is expressed as a sub-resource: `POST /context/`.
- **Optimistic concurrency via ETag / If-Match.** Every variant response carries a weak ETag derived from a SHA-256 hash of the three content fields (`html`, `css`, `javascript`). Clients must send the ETag back on `PUT /variants/{id}` as an `If-Match` header; mismatches return `412 Precondition Failed`. This is the same primitive the sync protocol will use for fast-forward detection in Phase 5 — the Phase 3 commit flow dogfoods the sync concurrency model.
- **Stateless sessions.** Editing sessions are a purely client-side convention stored under `.phoxtail/studio/<id>/` on disk. The API has no session endpoint; `phoxtail studio edit` bootstraps a session by calling `GET /variants/{id}` (capturing the ETag) and `POST /context/`, and `phoxtail studio commit` replays those fields via `PUT /variants/{id}` with `If-Match`.
- **Error shape.** 4xx responses currently return `{"detail": "..."}`; the field names are aligned with RFC 7807 Problem Details so we can harden the format without changing clients.
- **Discovery.** Django Ninja auto-generates an OpenAPI schema at `/api/openapi.json` and Swagger UI at `/api/docs`. That document is the machine-readable contract for every future remote, MCP tool, or third-party integration.

## Context assembly

The old `BlockSystemPrompt` model and its three DTL prompt templates (`variant_generator`, `variant_refiner`, `variant_editor`) have been replaced by a single static Jinja2 context template (`cli/templates/studio/context.md`) shipped with phoxtail. In the MCP/agent era, system prompts no longer need to carry task instructions or output format directives — the agent has tools for that. The context template provides pure domain knowledge: block schema, DTL rules, CSS architecture, design tokens, and the current variant's code.

- `POST /api/streams/v1/context/` — assembles structured context data (block schema as JSON, rendered collection design tokens, variant code, references).
- `phoxtail_get_context` (MCP tool) — calls the endpoint and renders the Jinja2 template into the final context document.
- `phoxtail studio context` (CLI) — same pipeline with Rich-formatted output.
- `VariantCollection.render() -> str` — renders a collection's design-token documentation (palettes, fonts, philosophy) by running the collection's own template. This is the only piece of the old DTL rendering pipeline that survives.

## Wagtail pages as the preview surface

Phoxtail Studio does not implement a live preview, and it does not need to. The designer opens any Wagtail page in the project that uses the variant being edited. Every `BlockVariant` save invalidates the relevant caches (signals already wired in [Performance](../engine/streams/performance.md)). The designer refreshes the page and sees the change — in realistic content, next to sibling blocks, under real responsive conditions.

For polish, `django-browser-reload` can be integrated in the dev environment so the tab refreshes automatically after every commit. This is optional and belongs to Phase 3 of the [roadmap](roadmap.md).

This choice is the single largest simplification in the whole design. The Wagtail page editor has spent years becoming a good preview of a Wagtail site. Re-implementing a live preview inside an admin view would have been the hardest part of the old Studio plan, and the payoff would have been smaller than what Wagtail already provides for free.

## Data flow: a refinement round

```
1. designer: phoxtail studio edit hero-centered
2. CLI → API → DB: SELECT the BlockVariant row + render system prompt
3. working copy appears at .phoxtail/studio/<session>/
   (template.html, style.css, script.js, context.md)
4. designer: cd into session, starts claude
5. designer + agent: iterate on the three files using the agent's built-in
   Read/Edit tools; the context.md file is the rendered system prompt
6. designer: phoxtail studio commit
7. CLI → API → DB: UPDATE the BlockVariant row, fire cache signals
8. designer: refresh Wagtail preview tab, inspect result
9. designer satisfied → done; not satisfied → back to 5
```

The working-copy-on-disk pattern is one of two valid flows. The other is MCP-direct: the agent calls `phoxtail_get_variant`, produces an edit in-conversation, calls `phoxtail_update_variant`, and never touches disk. Both flows are cheap to build on top of the same API layer, and the roadmap allows for both to coexist.

## Why surgical edits instead of full regeneration

The current Wagtail Studio flow asks the LLM to re-emit the entire HTML + CSS + JavaScript on every refinement round, because the prompt template's "Output Format" section demands it (see `variant_generator.md` and `variant_refiner.md`). This is expensive in tokens and encourages the model to inadvertently change code that was already good.

Phoxtail Studio reframes refinement as editing instead of generation. The agent reads the current files, produces a diff, writes the diff. This is exactly how Claude Code already works on source code; by putting variants on disk (or exposing them via MCP tools), the agent can apply its normal editing behavior to them.

This implies that the prompt templates shipped with Phoxtail Studio will eventually grow a third variant — `variant_editor.md` — that frames the task as targeted refinement rather than full regeneration. The existing `variant_generator.md` remains useful for initial creation; `variant_refiner.md` remains useful as a middle ground; `variant_editor.md` is the new low-token refinement mode.

## What was removed

The Wagtail-admin Stream Studio has been removed in favor of the CLI + MCP system:

- `BlockSystemPrompt` model and its three prompt templates
- `StudioViewSet`, `StudioContextForm`, all Studio search views
- The `templates/phoxtail_streams/studio/` template tree and `studio.css`
- The `access_stream_studio` permission
- The `/api/streams/v1/prompts/` endpoints
- The `minify` template tag
- Prompt-related CLI commands (`list prompts`, `show prompt`)

All variant editing is now done through the CLI (`phoxtail studio edit/commit`) or MCP tools (`phoxtail_get_variant`, `phoxtail_update_variant`, `phoxtail_get_context`).
