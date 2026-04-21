"""``phoxtail://page-types`` MCP resource.

Dynamic discovery endpoint — enumerates every page type that some
installed app has contributed via ``PhoxtailAppConfig.page_schema_contributors``.
The agent calls this before writing to learn which fields each page
type exposes and which MCP tool resolves each FK field to an ID.
"""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.pages._http import request, get_json
from phoxtail.mcp.pages.pages import _write_error_envelope



@mcp_server.resource(
    "phoxtail://page-types",
    name="Page Type Catalog",
    description=(
        "Enumerates every Wagtail Page subclass contributed by installed "
        "Phoxtail apps, with their writable fields and per-FK lookup tool "
        "names. Read this before editing pages so you know which fields "
        "exist for each page type and which MCP tool to call to resolve "
        "each FK (image, author, etc.) to an integer ID."
    ),
    mime_type="application/json",
)
def page_types_resource() -> str:
    resp = request("GET", "/page-types/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)
