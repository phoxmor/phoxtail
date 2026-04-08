# MCP Architecture

## Role

The MCP (Model Context Protocol) server is the AI-agent interface to Phoxtail. It exposes project operations as MCP tools so that Claude Code, Claude Desktop, or any MCP-aware client can interact with a Phoxtail project programmatically — listing resources, reading state, making edits, assembling context — without custom prompt engineering or manual copy-paste workflows.

Like the CLI, the MCP server is a first-class citizen of the Phoxtail package. It lives at `phoxtail/mcp/` alongside `phoxtail/api/` and `phoxtail/cli/`, at the same level of the package hierarchy. It is not a sub-feature of Studio — it is a project-wide surface that any domain can contribute tools to.

## Why a dedicated package

The MCP server started as a single file inside the Studio CLI (`phoxtail/cli/studio/mcp.py`). That was the right place for a Phase 4 prototype scoped to variant editing. But the MCP surface will grow beyond Studio:

- **Design tokens.** List palettes, inspect font families, pull tokens from a remote project. The models live in `phoxtail/design/`, not in `phoxtail/streams/`.
- **Pages and sites.** List sites, find pages, inspect block usage, translate content, switch collection themes across a site. The models live in the hatched project's app, not in any library app.
- **Cross-domain orchestration.** "Transform all blocks on My Awesome Site to use Material Design 3 variants" requires tools that span streams, design, and pages in a single agent conversation.

A single-file MCP server cannot scale to this. An MCP module nested inside `cli/studio/` would misrepresent the scope — Studio is one domain, not the whole project. A top-level `phoxtail/mcp/` package gives the MCP surface the same structural standing as the API and CLI, and the same room to grow.

## Package layout

```
phoxtail/mcp/
├── __init__.py              # FastMCP instance, tool module imports
├── _http.py                 # shared HTTP client (base URL, request, helpers)
│
├── studio/                  # domain: studio (variant editing, context)
│   ├── __init__.py
│   ├── variants.py          # list, get, update, create, diff
│   ├── collections.py       # list, get (rendered tokens)
│   ├── blocks.py            # list
│   └── context.py           # get_context (template rendering)
│
├── design/                  # domain: design tokens (future)
│   ├── __init__.py
│   ├── palettes.py          # list, get, inspect palette roles
│   └── fonts.py             # list, get font families and weights
│
└── pages/                   # domain: pages and sites (future)
    ├── __init__.py
    ├── sites.py             # list sites, get site config
    ├── pages.py             # find, inspect, translate pages
    └── theming.py           # switch collections, inspect theme state
```

### Why this shape

**One `FastMCP` instance.** Defined in `phoxtail/mcp/__init__.py`. Every domain module registers its tools on this single instance. A single MCP server means the agent sees all available tools in one tool list and can orchestrate across domains without switching servers or managing multiple connections.

**Domain-aligned sub-packages, not app-aligned.** This is the key difference from the API layer. The API mirrors Django apps because its job is to expose models — the app boundary is the right boundary. The MCP layer mirrors business domains because its job is to enable workflows — and workflows cross app boundaries.

`studio/` is the clearest example: it orchestrates across `streams` (variants, blocks), `design` (collection tokens), and potentially `pages` (preview surfaces). Its tools exist to serve the variant-editing workflow, not to mirror the `streams` app's model structure. Similarly, a future `theming/` domain might combine tools that read from `design` (palettes, fonts) and write to `pages` (site config) — no single Django app owns that workflow.

Some domains will align with a single app (e.g. `design/` tools may map 1:1 to `api/design/v1/` endpoints). That's fine. The point is that the organizing principle is the domain concern, not the ORM layer. The business logic dictates the names and structure.

**Sub-packages, not flat files.** The current `mcp.py` is ~440 lines with 8 tools. The Studio domain alone will grow to include session management, sync-related tools, and richer context assembly. Each domain gets a sub-package with one module per resource group, matching the API's structure within each version directory.

## The single server

All tools from all domains register on one `FastMCP` instance. This is a deliberate choice:

```python
# phoxtail/mcp/__init__.py
from mcp.server.fastmcp import FastMCP

mcp_server = FastMCP(
    "phoxtail",
    instructions="...",
)

# Each domain module imports mcp_server and decorates its tools
from phoxtail.mcp.studio import variants, collections, blocks, context  # noqa: F401, E402
# from phoxtail.mcp.design import palettes, fonts                      # noqa: future
# from phoxtail.mcp.pages import sites, pages, theming                 # noqa: future
```

A single server matters because:

1. **Agents reason about tool lists, not server topology.** When the agent sees `phoxtail_studio_list_variants` and `phoxtail_pages_find_page` in the same tool list, it can plan a multi-step workflow that spans both. Separate servers would require the agent (or the user) to know which server handles which tool.
2. **One `.mcp.json` entry.** The user registers one server, not N. Adding a new domain is invisible to the user's configuration.
3. **Shared HTTP plumbing.** Every tool talks to the same API server. The base URL, timeout, config loading, and error handling live in `_http.py` once.

## Tool naming convention

Tools are namespaced to help the agent navigate the surface:

```
phoxtail_{domain}_{action}_{resource}
```

Examples from Studio:

```
phoxtail_studio_list_variants
phoxtail_studio_get_variant
phoxtail_studio_update_variant
phoxtail_studio_create_variant
phoxtail_studio_diff_variant
phoxtail_studio_get_context
phoxtail_studio_list_collections
phoxtail_studio_get_collection
phoxtail_studio_list_blocks
```

Future examples from other domains:

```
phoxtail_design_list_palettes
phoxtail_design_get_palette
phoxtail_design_list_fonts

phoxtail_pages_list_sites
phoxtail_pages_find_page
phoxtail_pages_get_page
phoxtail_pages_translate_page
phoxtail_pages_switch_collection
```

This convention gives the agent three benefits:

1. **Scoping.** "The user asked about design tokens — I should look at `phoxtail_design_*` tools." The domain segment acts as a filter.
2. **Workflow discovery.** Tools in the same domain group are likely used together. The agent can scan `phoxtail_studio_*` to understand the variant editing workflow.
3. **Reduced confusion.** The agent doesn't consider variant editing tools when the user asks about page translation. Domain boundaries in the tool names create conceptual boundaries in the agent's reasoning.

### Migration from current names

The current tools use a flat naming scheme (`phoxtail_list_variants`, `phoxtail_get_variant`, etc.). When the package is restructured, these will be renamed to include the domain segment (`phoxtail_studio_list_variants`, etc.). Since MCP tool names are not a versioned public contract — they are consumed by agents in real-time from the tool list — this is a clean rename, not a breaking change.

## Relationship to the API

Every MCP tool is a thin wrapper around an API endpoint. The MCP layer does not import Django models, does not run ORM queries, and does not access the database. It issues HTTP requests against the running application, exactly like the CLI:

```
Agent ──► MCP tool ──► HTTP ──► API endpoint ──► Django ORM ──► Database
```

This boundary is the same one the CLI respects, and for the same reasons:

- MCP tools can be tested against a mock HTTP server without Django.
- The API can evolve its internals without breaking MCP tools, as long as the HTTP contract holds.
- MCP tools cannot do anything the API does not expose. There are no backdoors.

The MCP layer adds three things on top of the raw API responses:

1. **Tool metadata.** Names, descriptions, and parameter schemas that help the agent understand what each tool does and when to use it.
2. **Response formatting.** Some tools render API responses through Jinja2 templates (e.g. `get_context` assembles a rich Markdown briefing from structured API data). Others return raw JSON.
3. **Error translation.** HTTP status codes are translated into structured error objects that the agent can reason about (e.g. `412 → {"error": "conflict", "detail": "..."}`).

## Server instructions

The `FastMCP` instance carries an `instructions` field — a natural-language briefing that MCP clients present to the agent alongside the tool list. This is the agent's entry point to understanding the Phoxtail domain:

```python
mcp_server = FastMCP(
    "phoxtail",
    instructions=(
        "Phoxtail tools for managing a Phoxtail project. "
        "Tools are organized by domain: studio (variant editing), "
        "design (design tokens), pages (sites and content). "
        "Use phoxtail_studio_* tools for block variant operations. "
        "Use phoxtail_design_* tools for palettes and fonts. "
        "Use phoxtail_pages_* tools for sites, pages, and theming. "
        "Always fetch a resource before updating it to get the "
        "current ETag for concurrency control."
    ),
)
```

The instructions serve as a domain map. They tell the agent which tool group to reach for based on the user's intent. As new domains are added, the instructions are updated to include them.

## The CLI entry point

The MCP server is started via a CLI command. After the restructure, the `serve` command moves from `phoxtail studio mcp serve` to a top-level position that reflects the server's project-wide scope:

```
phoxtail mcp serve
```

The command is a thin wrapper:

```python
from phoxtail.mcp import mcp_server

def serve():
    mcp_server.run(transport="stdio")
```

The `.mcp.json` configuration for Claude Code registers this command:

```json
{
  "mcpServers": {
    "phoxtail": {
      "command": "phoxtail",
      "args": ["mcp", "serve"]
    }
  }
}
```

Note the server name changes from `phoxtail-studio` to `phoxtail` — it is no longer scoped to Studio.

## Shared HTTP layer

`phoxtail/mcp/_http.py` extracts the HTTP client plumbing that currently lives in `mcp.py`. All tool modules import from it:

```python
from phoxtail.mcp._http import get_json, request
```

The module provides:

- `api_base_url()` — reads the base URL from `phoxtail.toml` or falls back to `http://localhost`.
- `request(method, path, ...)` — issues an HTTP request against the API, returning the raw `httpx.Response`.
- `get_json(path, **params)` — convenience for GET requests that return JSON.

This is the same HTTP client the CLI uses (`phoxtail/cli/studio/client.py`), but adapted for MCP's error-handling style (raise exceptions instead of calling `typer.Exit`).

## Context rendering

Some MCP tools return more than raw JSON. The `get_context` tool, for example, calls `POST /api/streams/v1/context/` to get structured data, then renders it through a Jinja2 template into a rich Markdown document that the agent can read as a domain briefing.

Context templates live in `phoxtail/cli/templates/studio/` (shared with the CLI's `phoxtail studio context` command). The MCP layer imports the template environment and renders the same templates. This ensures that the CLI and MCP surfaces produce identical context documents.

As new domains add their own context assembly (e.g. a design-token briefing for the `design` domain), they follow the same pattern: API endpoint returns structured data, MCP tool renders it through a domain-specific template.

## Adding a new domain

Adding MCP tools for a new domain follows a consistent pattern:

1. **Ensure API endpoints exist.** The MCP layer consumes the API — if the endpoints don't exist yet, build them first in `phoxtail/api/<app>/v1/`.
2. **Create `phoxtail/mcp/<domain>/`** with `__init__.py` and one module per resource group.
3. **Import `mcp_server`** from `phoxtail.mcp` and decorate tool functions with `@mcp_server.tool(name="phoxtail_<domain>_<action>_<resource>", description="...")`.
4. **Import the domain modules** in `phoxtail/mcp/__init__.py` so the tools are registered at server startup.
5. **Update the server instructions** to mention the new domain.

The pattern is proven. `studio/` is the reference implementation.

## What the MCP layer does not do

- **Sync operations.** Pull, push, publish, and fork are deliberate human decisions. They are CLI commands, not MCP tools. An agent should never trigger a sync operation without explicit human initiation.
- **Destructive operations without concurrency control.** Every write tool requires an ETag. The agent must read before writing. There is no "force update" tool.
- **Direct model access.** The MCP layer does not import Django models or bypass the API. If something isn't exposed as an API endpoint, it isn't available as an MCP tool.
- **Session management on behalf of the user.** The CLI's working-copy sessions (`.phoxtail/studio/<id>/`) are a human workflow. The MCP server operates statelessly — it reads, edits, and writes through the API without creating local session state.

## What this enables

With the MCP server structured as a project-wide surface, the following workflows become possible in a single agent conversation:

- "List all variants in the hero block and show me the one from the ground-state collection" — `phoxtail_studio_list_variants` + `phoxtail_studio_get_variant`
- "Get the full context for editing this variant, then update its CSS" — `phoxtail_studio_get_context` + `phoxtail_studio_update_variant`
- "Show me the palettes available in this project" — `phoxtail_design_list_palettes`
- "Find the homepage of My Awesome Site and translate it to German" — `phoxtail_pages_list_sites` + `phoxtail_pages_find_page` + `phoxtail_pages_translate_page`
- "Switch all blocks on My Awesome Site to use the Material Design 3 collection" — `phoxtail_pages_list_sites` + `phoxtail_studio_list_variants` + `phoxtail_pages_switch_collection`

The last example crosses three domains (pages, studio, pages) in a single workflow. A single MCP server makes this natural. Isolated per-domain servers would make it awkward.
