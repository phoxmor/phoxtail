"""MCP (Model Context Protocol) server for Phoxtail Studio.

Exposes Studio operations as MCP tools so that AI agents (Claude Code,
Claude Desktop, or any MCP-aware client) can list, read, edit, and create
block variants without a working-copy detour.

Each tool is a thin wrapper around the same ``/api/streams/v1/`` endpoints
that the CLI consumes. The MCP server does not introduce its own logic —
it cannot do anything the CLI cannot.

Sync commands are intentionally excluded from the MCP surface. Sync is a
deliberate human decision, not something an agent should trigger.

Usage::

    phoxtail studio mcp serve

Or via ``.mcp.json`` in the project root::

    {
      "mcpServers": {
        "phoxtail-studio": {
          "command": "phoxtail",
          "args": ["studio", "mcp", "serve"]
        }
      }
    }
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import typer
from jinja2 import Environment, FileSystemLoader
from mcp.server.fastmcp import FastMCP

from phoxtail.cli.utils.config import _find_config_file, load_config

# ---------------------------------------------------------------------------
# Context template
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "studio"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=True,
)

app = typer.Typer(help="MCP server for AI agents.")

# ---------------------------------------------------------------------------
# HTTP plumbing — mirrors client.py but returns data instead of exiting
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/streams/v1"
DEFAULT_TIMEOUT = 30.0


def _api_base_url() -> str:
    if _find_config_file() is None:
        return DEFAULT_BASE_URL
    try:
        config = load_config()
    except Exception:
        return DEFAULT_BASE_URL
    studio = config.get("studio") or {}
    url = studio.get("api_url") or DEFAULT_BASE_URL
    return url.rstrip("/")


def _url(path: str) -> str:
    return f"{_api_base_url()}{API_PREFIX}{path}"


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Issue an HTTP request, returning the raw response.

    Unlike the CLI client, errors are raised as exceptions (caught by the
    MCP tool wrappers) rather than calling ``typer.Exit``.
    """
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    response = httpx.request(
        method,
        _url(path),
        params=clean_params or None,
        json=json_body,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )
    return response


def _get_json(path: str, **params: Any) -> dict[str, Any]:
    resp = _request("GET", path, params=params)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp_server = FastMCP(
    "phoxtail-studio",
    instructions=(
        "Phoxtail Studio tools for managing block variants — the HTML, CSS, "
        "and JavaScript implementations that power Phoxtail project pages. "
        "Use list tools to discover available blocks, collections, and variants. "
        "Use phoxtail_get_context to get a full briefing (block schema, DTL "
        "rules, design tokens, current code) before editing or creating. "
        "Use update/create tools to make changes. Always fetch a variant "
        "before updating it so you have the current ETag for concurrency "
        "control."
    ),
)


# -- Listing tools ---------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_list_variants",
    description=(
        "List all block variants in the project. "
        "Optionally filter by block identifier and/or collection identifier. "
        "Returns a summary of each variant (identifier, name, description, "
        "block, collection, is_default) without the full HTML/CSS/JS content."
    ),
)
def list_variants(
    block: str | None = None,
    collection: str | None = None,
) -> str:
    data = _get_json("/variants/", block=block, collection=collection)
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_list_collections",
    description=(
        "List all variant collections in the project. "
        "A collection groups variants under a shared design system "
        "(e.g. 'ground-state', 'material-design')."
    ),
)
def list_collections() -> str:
    return json.dumps(_get_json("/collections/"), indent=2)


@mcp_server.tool(
    name="phoxtail_list_blocks",
    description=(
        "List all blocks in the project. "
        "A block is a structural schema (e.g. 'header_section', 'hero') "
        "that variants implement."
    ),
)
def list_blocks() -> str:
    return json.dumps(_get_json("/blocks/"), indent=2)


# -- Read tools ------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_get_collection",
    description=(
        "Get a collection's rendered design tokens — the palette roles, "
        "font roles, color strategy, and typography guidelines that define "
        "the design system. Use this when creating a variant for a "
        "different collection than the source variant, or when you need "
        "to understand a collection's design principles."
    ),
)
def get_collection(identifier: str) -> str:
    resp = _request("POST", f"/collections/{identifier}/render/")
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_get_variant",
    description=(
        "Get the full detail of a single block variant, including its HTML, "
        "CSS, and JavaScript content. Also returns the current ETag which "
        "MUST be passed to phoxtail_update_variant for concurrency control. "
        "Both identifier and block are required. Use collection to further "
        "disambiguate if the identifier exists in multiple collections."
    ),
)
def get_variant(
    identifier: str,
    block: str,
    collection: str | None = None,
) -> str:
    resp = _request(
        "GET",
        f"/variants/{identifier}/",
        params={"block": block, "collection": collection},
    )
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_get_context",
    description=(
        "Get the full context document for working with a block variant. "
        "Returns a rendered briefing that includes the block's field schema, "
        "DTL syntax reference, CSS architecture rules, the variant's "
        "collection design tokens, the current variant's code, and "
        "optionally reference variants for inspiration. "
        "Call this before editing a variant to understand the domain "
        "constraints. To inspect a different collection's design system "
        "(e.g. for cross-collection creation), use phoxtail_get_collection."
    ),
)
def get_context(
    block: str,
    variant: str,
    references: list[str] | None = None,
) -> str:
    body: dict[str, Any] = {"block": block, "variant": variant}
    if references:
        body["references"] = references
    resp = _request("POST", "/context/", json_body=body)
    resp.raise_for_status()

    data = resp.json()
    template = _jinja_env.get_template("context.md")
    return template.render(**data)


# -- Diff tool -------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_diff_variant",
    description=(
        "Show a unified diff between a variant's current content in the "
        "database and proposed new content. Pass the fields you intend to "
        "change (html, css, javascript); omitted fields are not diffed. "
        "Use this to preview changes before calling phoxtail_update_variant."
    ),
)
def diff_variant(
    identifier: str,
    block: str,
    html: str | None = None,
    css: str | None = None,
    javascript: str | None = None,
    collection: str | None = None,
) -> str:
    resp = _request(
        "GET",
        f"/variants/{identifier}/",
        params={"block": block, "collection": collection},
    )
    resp.raise_for_status()
    current = resp.json()

    parts: list[str] = []
    for field, new_value in [
        ("html", html),
        ("css", css),
        ("javascript", javascript),
    ]:
        if new_value is None:
            continue
        old_lines = current[field].splitlines(keepends=True)
        new_lines = new_value.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{field}",
            tofile=f"b/{field}",
        )
        parts.append("".join(diff))

    result = "\n".join(p for p in parts if p)
    return result or "(no differences)"


# -- Write tools -----------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_update_variant",
    description=(
        "Update a variant's HTML, CSS, and/or JavaScript content. "
        "Requires the ETag from a prior phoxtail_get_variant call for "
        "optimistic concurrency control — if the variant has been modified "
        "since you read it, the update will fail with a conflict error. "
        "Omitted fields are left untouched. "
        "On success, returns the updated variant with a new ETag."
    ),
)
def update_variant(
    identifier: str,
    block: str,
    etag: str,
    html: str | None = None,
    css: str | None = None,
    javascript: str | None = None,
    collection: str | None = None,
) -> str:
    body: dict[str, Any] = {}
    if html is not None:
        body["html"] = html
    if css is not None:
        body["css"] = css
    if javascript is not None:
        body["javascript"] = javascript

    resp = _request(
        "PUT",
        f"/variants/{identifier}/",
        params={"block": block, "collection": collection},
        json_body=body,
        headers={"If-Match": etag},
    )
    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The variant has been modified since you last read it. "
                    "Call phoxtail_get_variant again to get the current "
                    "content and ETag, then retry."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required. Call phoxtail_get_variant first and "
                    "pass the _etag value from the response."
                ),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_create_variant",
    description=(
        "Create a new block variant. Requires an identifier (unique within "
        "the block+collection pair), a human-readable name, and the "
        "identifiers of an existing block and collection. "
        "Content fields (html, css, javascript) default to empty strings. "
        "Returns the created variant with its ETag."
    ),
)
def create_variant(
    identifier: str,
    name: str,
    block: str,
    collection: str,
    description: str = "",
    html: str = "",
    css: str = "",
    javascript: str = "",
) -> str:
    resp = _request(
        "POST",
        "/variants/",
        json_body={
            "identifier": identifier,
            "name": name,
            "block": block,
            "collection": collection,
            "description": description,
            "html": html,
            "css": css,
            "javascript": javascript,
        },
    )
    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "Variant already exists."),
            }
        )
    if resp.status_code == 404:
        return json.dumps(
            {
                "error": "not_found",
                "detail": resp.json().get("detail", "Block or collection not found."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Typer command
# ---------------------------------------------------------------------------


@app.command("serve")
def serve() -> None:
    """Start the MCP stdio server for AI agents.

    This command is intended to be launched by MCP clients (Claude Code,
    Claude Desktop) via their ``.mcp.json`` configuration, not by the
    user directly.
    """
    # FastMCP.run(transport="stdio") handles the stdio read/write loop.
    # Suppress any Rich/Typer output that might corrupt the JSON-RPC stream.
    sys.stderr.write("Phoxtail Studio MCP server starting (stdio)...\n")
    mcp_server.run(transport="stdio")
