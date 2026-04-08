"""MCP tools for listing blocks."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import get_json


@mcp_server.tool(
    name="phoxtail_studio_list_blocks",
    description=(
        "List all blocks in the project. "
        "A block is a structural schema (e.g. 'header_section', 'hero') "
        "that variants implement."
    ),
)
def list_blocks() -> str:
    return json.dumps(get_json("/blocks/"), indent=2)
