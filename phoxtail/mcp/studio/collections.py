"""MCP tools for listing and inspecting variant collections."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import get_json


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
        "Get a collection's design guidelines — the philosophy, "
        "principles, and design patterns that define this collection's "
        "character. Use this when creating a variant for a different "
        "collection than the source variant, or when you need to "
        "understand a collection's design approach. Design tokens "
        "(palette roles, font roles) are provided separately via "
        "the context tool."
    ),
)
def get_collection(identifier: str) -> str:
    return json.dumps(get_json(f"/collections/{identifier}/"), indent=2)
