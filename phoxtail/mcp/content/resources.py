"""``phoxtail_page_types_list`` MCP tool.

Discovery tool — enumerates every page type that some installed app has
contributed via ``PhoxtailAppConfig.page_schema_contributors``. Agents
call this before creating or editing pages to learn which fields each
page type exposes, which are required on creation, and which MCP tool
resolves each FK field to an integer ID.
"""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import request
from phoxtail.mcp.content.pages import _write_error_envelope


@mcp_server.tool(
    name="phoxtail_locales_list",
    description=(
        "List all Wagtail locales configured in this project. Returns each "
        "locale's id (integer) and language_code (e.g. 'en', 'fr'). "
        "Use the id as the locale_id argument for phoxtail_pages_translate_page."
    ),
)
def locales_list() -> str:
    resp = request("GET", "/locales/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_page_types_list",
    description=(
        "List every Wagtail Page subclass contributed by installed Phoxtail "
        "apps. Returns each type's content_type string, its writable fields "
        "(with type and required flag), and fk_lookups mapping FK fields to "
        "the MCP tool that resolves names to IDs. Call this before "
        "phoxtail_pages_create_page so you know which fields are required "
        "and how to resolve FK values."
    ),
)
def page_types_list() -> str:
    resp = request("GET", "/page-types/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)
