# Implementation Roadmap

The plan is staged so that each phase is useful on its own and the whole thing can be paused, redirected, or rolled back at any phase boundary. No phase depends on a later phase landing.

Deliverables are scoped so that each phase can be completed and reviewed in isolation. Exit criteria are concrete and testable.

## Phase 0 — CLI scaffold

**Goal:** Prove the wiring. No feature value yet.

- Create `phoxtail/cli/studio.py` as a Typer sub-app.
- Register it in `phoxtail/__main__.py` alongside the existing sub-apps (`docker`, `db`, `env`, etc.).
- Implement one trivial command: `phoxtail studio version`, printing the Studio sub-app version (may be the same as the Phoxtail version for now).
- Write a test that invokes the command and asserts on its output.

**Exit criterion:** `phoxtail studio version` runs successfully inside a hatched project and prints a version string. `phoxtail studio --help` lists the sub-app.

## Phase 1 — Inspection

**Goal:** Fully browse a project's Studio state from the terminal.

- Add Django Ninja API endpoints on the running app at `/api/streams/v1/`:
    - `GET /variants` (with `?block=`, `?collection=` query filters)
    - `GET /variants/{identifier}` (sets `ETag` header)
    - `GET /collections`
    - `GET /collections/{identifier}`
    - `GET /blocks`
    - `GET /blocks/{identifier}`
    - ~~`GET /prompts`~~ (removed in Phase 4)
    - ~~`GET /prompts/{identifier}`~~ (removed in Phase 4)
- All endpoints return JSON through Pydantic v2 schemas (the stable contract for agents, scripts, and remote sync peers).
- The API layer lives in a top-level `phoxtail/api/` package that mirrors the app layout (`phoxtail/api/streams/v1/...`), so adding a future `phoxtail/api/design/v1/` is a two-line change in `phoxtail/api/__init__.py`.
- Wire each endpoint to a Typer command on `phoxtail studio list` and `phoxtail studio show`. The CLI calls the API via `httpx`.
- Tests cover the Pydantic schema shapes and API response codes.

**Exit criterion:** A designer can fully explore their project's Studio state from the terminal without opening the Wagtail admin.

## Phase 2 — Prompt rendering

**Goal:** Replace the Wagtail-admin Studio's "copy prompt to clipboard" workflow entirely.

- ~~API endpoint `POST /api/streams/v1/prompts/{template-identifier}/render`~~ (removed in Phase 4 — replaced by `POST /api/streams/v1/context/`)
- ~~CLI command `phoxtail studio prompt`~~ (removed in Phase 4 — replaced by `phoxtail studio context`)
- Context assembly now uses a static Jinja2 template instead of `BlockSystemPrompt.render()`.

**Exit criterion:** Every workflow currently served by the Wagtail-admin Studio's prompt assembly is served by `phoxtail studio context`. ~~No new functionality; feature parity at the terminal.~~ Superseded by the context-based approach in Phase 4.

## Phase 3 — Editing sessions

**Goal:** Close the refinement loop — edit a variant with an agent, commit, preview.

- Introduce the `.phoxtail/studio/<session-id>/` working-copy convention. Session metadata lives in `session.json` and includes the ETag captured when the session was created, so that `commit` can send it back as `If-Match`.
- No new API endpoints: sessions are a client-side convention and reuse the Phase 1-2 surface. `phoxtail studio edit` calls `GET /variants/{id}` (capturing the ETag) and `POST /prompts/{template}/render`. `phoxtail studio commit` calls `PUT /variants/{id}` with the stored `If-Match` header.
- A mismatched ETag returns `412 Precondition Failed`; the CLI surfaces the conflict and preserves the session so the user can resolve it.
- CLI commands: `phoxtail studio edit`, `commit`, `discard`, `sessions`. Session listing and discarding are host-side filesystem operations handled entirely by the CLI — there is no server-side session state.
- On `commit`, the `PUT` endpoint saves the `BlockVariant` row, which fires the cache invalidation signals already wired in the streams engine.
- `django-browser-reload` is already configured in the project template's development settings — Wagtail preview tabs refresh automatically.
- Ship a new prompt template `variant_editor.md` that frames the task as targeted edit rather than full regeneration, reducing per-round tokens.

**Exit criterion:** A designer can run `phoxtail studio edit hero-centered`, `cd` into the session directory, run `claude`, iterate with the agent using only built-in Read and Edit tools, run `phoxtail studio commit`, and see the change in a Wagtail preview tab. The session lifecycle is fully managed by the CLI.

**Deprecation checkpoint:** At the end of Phase 3, the Wagtail-admin Stream Studio is functionally redundant. Hide it from the menu, mark it deprecated in the docs, keep the code in place for one more release for safety.

## Phase 4 — MCP server

**Goal:** Make Studio operations first-class tools for AI agents, without requiring a working-copy detour.

- New module `phoxtail/cli/studio/mcp.py` that implements an MCP stdio server.
- Exposes tools mirroring the Phase 1-3 verbs: `phoxtail_list_variants`, `phoxtail_get_variant`, `phoxtail_get_context`, `phoxtail_diff_variant`, `phoxtail_update_variant`, `phoxtail_create_variant`, `phoxtail_get_collection`. Each tool calls the corresponding `/api/streams/v1/` endpoint.
- **Completed:** Replaced `BlockSystemPrompt` model and prompt-render pipeline with a static Jinja2 context template. Removed the old Wagtail admin Studio interface, `access_stream_studio` permission, and all prompt-related API/CLI commands.
- Sync commands are _not_ exposed in the MCP surface in this phase. Sync is a deliberate human decision.
- Ship an example `.mcp.json` fragment users can drop into their project to register the server with Claude Code.
- Document the MCP tool schemas in the [CLI Reference](cli.md) and in a new MCP-specific page if the surface grows.

**Exit criterion:** A designer runs `claude` in a Phoxtail project with the MCP server registered, and Claude can list, read, edit, and save variants without any working-copy step. The Phase 3 working-copy flow remains available in parallel for designers who prefer it or for non-MCP agents.

## Phase 5 — Sync v1 (peer-to-peer)

**Goal:** Move a variant between two Phoxtail projects.

- New model(s) to track sync identity, version, source, and parent version for each synchronizable entity. Migration included.
- New sync-specific endpoints (`/api/streams/v1/sync/...` or a dedicated `v2` cut if the shape breaks) for export, import, and remote management.
- CLI: `phoxtail studio pull`, `push`, `fork`, `remote add/list/remove`.
- The existing `/api/streams/v1/` surface already lets any Phoxtail project act as a remote for another — Phase 3's ETag/`If-Match` plumbing is the same primitive sync uses for fast-forward detection, so a remote `GET /variants/{id}` with `If-None-Match` is a no-op pull at the protocol level. Read-only remotes work out of the box; authenticated writes arrive in this phase.
- Authentication: static bearer tokens stored in `phoxtail.toml`. No user identities yet.
- Conflict detection only; three-way merge is deferred to Phase 5.1 if needed.

**Exit criterion:** Two hatched Phoxtail projects on localhost can push and pull a variant between themselves end-to-end, with version tracking and fast-forward detection working correctly.

## Phase 6 — Central registry

**Goal:** A public hub for variants.

- Stand up a dedicated Phoxtail project (likely `phoxtail.com`) configured as a registry instance.
- Discovery API: search by name, tag, collection, block type, author.
- Web UI for browsing published variants and collections, including preview screenshots.
- Attribution and license fields on published entities.
- `phoxtail studio publish` as the canonical publication flow.
- Per-user identities and namespace ownership.

**Exit criterion:** A designer can run `phoxtail studio publish` from a local project, and the result appears in a public index that other projects can `phoxtail studio pull` from.

## Phase 7 — Marketplace features

**Goal:** Commercial viability for variant authors.

- Private registries for organizations.
- Paid collections with licensing enforcement.
- Rich previews (screenshots, sample renders, responsive previews).
- Subscription and update notifications (`phoxtail studio pull --subscribe`).
- Curation tooling for registry operators.

This phase is sketched, not planned. Its features will be validated against demand from the earlier phases before investment.

## Deprecation schedule

| Component | Deprecated in | Removed in |
|---|---|---|
| `BlockSystemPrompt` model, prompt templates, prompt API | End of Phase 3 | **Phase 4 (done)** |
| Wagtail admin Studio menu entry, views, forms, templates, CSS | End of Phase 3 | **Phase 4 (done)** |
| `access_stream_studio` permission | End of Phase 3 | **Phase 4 (done)** |
| `streams/management/data/blocks/<...>/template.html` files as the authoritative source | Phase 5 | Phase 6 (replaced by a bootstrap registry collection) |
| `populate_streams` reseed behavior overwriting DB edits | Phase 3 | Phase 5 |

Nothing is removed eagerly. Every removal happens after the replacement has been in use long enough to be trusted, and after at least one release cycle of deprecation warnings.

## What we are deliberately not doing

- No real-time multi-user collaboration on a single variant.
- No graphical design tools. Terminal and code editor, always.
- No automatic schema migration for Block schema drift across projects.
- No bundled binary assets in sync v1 (URL references only).
- No agent-initiated sync operations (pull/push/publish are human decisions, never MCP tools).

Each of these could be added later without breaking the core protocol or the CLI surface. They are excluded now to keep the early phases shippable.
