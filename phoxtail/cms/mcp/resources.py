"""``phoxtail_locales_list`` and ``phoxtail_page_types_list`` MCP tools.

Discovery tool — enumerates every page type that some installed app has
contributed through ``page_schemas`` in its ``api/`` package. Agents
call this before creating or editing pages to learn which fields each
page type exposes, which are required on creation, and which MCP tool
resolves each FK field to an integer ID.

The two tools here are the two kinds of catalogue, and they are gated
differently on purpose. ``phoxtail_locales_list`` names
``wagtailcore.view_locale``, because ``Locale`` is a model with rows and a
real grant over them. ``phoxtail_page_types_list`` names nothing, matching
the endpoint it calls: what that returns is derived from installed code
rather than from rows, so there is no permission to name — and that
endpoint says so with ``authenticated()`` rather than by staying silent,
since a bare endpoint keeps the API-wide default and refuses a scoped
token while a bare tool is offered to *every* credential.
"""

from __future__ import annotations

import json

from phoxtail.cms.mcp._http import request
from phoxtail.cms.mcp.pages import _write_error_envelope
from phoxtail.mcp import mcp_server
from phoxtail.mcp.authorization import scoped
from phoxtail.mcp.pagination import DEFAULT_LIMIT, PAGED, Limit, Offset


@mcp_server.tool(
    name="phoxtail_locales_list",
    auth=[scoped("wagtailcore.view_locale")],
    description=(
        "List all Wagtail locales configured in this project. Returns each "
        "locale's id (integer) and language_code (e.g. 'en', 'fr'). "
        "Use the id as the locale_id argument for phoxtail_pages_translate_page. " + PAGED
    ),
)
def locales_list(limit: Limit = DEFAULT_LIMIT, offset: Offset = 0) -> str:
    resp = request("GET", "/locales/", params={"limit": limit, "offset": offset})
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
