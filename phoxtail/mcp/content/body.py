"""``phoxtail_pages_*_body`` MCP tools — read + replace a page's body."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import request
from phoxtail.mcp.content.pages import _write_error_envelope


@mcp_server.tool(
    name="phoxtail_pages_get_body",
    description=(
        "Fetch a page's StreamField body as a list of {type, value, id} "
        "blocks. Returns an object with `body` and `_etag` — the ETag "
        "is the page-level tag and MUST be passed back on "
        "phoxtail_pages_replace_body for concurrency control."
    ),
)
def get_body(page_id: int) -> str:
    resp = request("GET", f"/pages/{page_id}/body/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_pages_replace_body",
    description=(
        "Replace a page's body wholesale with a new list of blocks. "
        "Creates a draft revision; does NOT publish. The body must be "
        "a list of {type, value, id} dicts — use phoxtail_studio_list_blocks "
        "to discover available block types, phoxtail_studio_list_variants "
        "to discover variant IDs (the integer `id` field, NOT the string "
        "`identifier`), and phoxtail://schema-reference to "
        "understand each block's `value` shape. `id` can be omitted for "
        "new blocks; the server will generate UUIDs. Pass `etag` from a "
        "prior phoxtail_pages_get_body or phoxtail_pages_get_page."
    ),
)
def replace_body(
    page_id: int,
    etag: str,
    body: list[dict[str, Any]],
) -> str:
    resp = request(
        "PUT",
        f"/pages/{page_id}/body/",
        json_body={"body": body},
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)
