"""MCP resources for the studio domain."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.studio._http import request, get_json


@mcp_server.resource(
    "phoxtail://schema-reference",
    name="Schema Field Reference",
    description=(
        "Complete catalog of available schema field types and their "
        "parameters for designing block schemas. Includes field types "
        "(char, text, image, etc.), structure types (struct, list_struct, "
        "stream), and nesting layer types."
    ),
    mime_type="application/json",
)
def schema_reference() -> str:
    return json.dumps(get_json("/schema-catalog/"), indent=2)
