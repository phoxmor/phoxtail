"""``phoxtail_pages_list_*`` MCP tools for image + document lookup."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.pages._http import request
from phoxtail.mcp.pages.pages import _write_error_envelope


def _lookup(path: str, search: str | None, limit: int) -> str:
    resp = request("GET", path, params={"search": search, "limit": limit})
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_list_images",
    description=(
        "Search images in the Wagtail library by title. Returns a list "
        "of {id, title, file_url}. The integer `id` is the value to pass "
        "wherever a block or page field expects an Image FK."
    ),
)
def list_images(search: str | None = None, limit: int = 50) -> str:
    return _lookup("/media/images/", search, limit)


@mcp_server.tool(
    name="phoxtail_pages_list_documents",
    description=(
        "Search documents in the Wagtail library by title. Returns a list "
        "of {id, title, file_url}. The integer `id` is the value to pass "
        "wherever a block or page field expects a Document FK."
    ),
)
def list_documents(search: str | None = None, limit: int = 50) -> str:
    return _lookup("/media/documents/", search, limit)
