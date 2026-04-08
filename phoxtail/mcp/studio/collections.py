"""MCP tools for listing and inspecting variant collections."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import get_json, request


@mcp_server.tool(
    name="phoxtail_studio_list_collections",
    description=(
        "List all variant collections in the project. "
        "A collection groups variants under a shared design system "
        "(e.g. 'ground-state', 'material-design')."
    ),
)
def list_collections() -> str:
    return json.dumps(get_json("/collections/"), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_get_collection",
    description=(
        "Get a collection's rendered design tokens — the palette roles, "
        "font roles, color strategy, and typography guidelines that define "
        "the design system. Use this when creating a variant for a "
        "different collection than the source variant, or when you need "
        "to understand a collection's design principles."
    ),
)
def get_collection(identifier: str) -> str:
    resp = request("POST", f"/collections/{identifier}/render/")
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)
