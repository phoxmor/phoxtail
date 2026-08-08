"""``phoxtail_pages_*_block`` MCP tools — surgical per-block CRUD + move."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp._changes import mark_changed_blocks
from phoxtail.mcp.content._http import request
from phoxtail.mcp.content.pages import _write_error_envelope


@mcp_server.tool(
    name="phoxtail_pages_get_block",
    description=(
        "Fetch a single block from a page's StreamField body by its UUID. "
        "Returns {block: {type, value, id}, _etag}. "
        "The _etag is the page-level ETag and MUST be passed back to any "
        "write call targeting this page (update, add, delete, move)."
    ),
)
def get_block(page_id: int, block_uuid: str) -> str:
    resp = request("GET", f"/pages/{page_id}/blocks/{block_uuid}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_update_block",
    description=(
        "Update the value of a single block in-place, identified by its UUID. "
        "Finds the block, replaces its value, saves a draft revision. "
        "Does NOT publish — the page remains as a draft for review. "
        "Pass etag from a prior phoxtail_pages_get_block or phoxtail_pages_get_body. "
        "Returns {block: {type, value, id}, _etag, _changed_blocks: [uuid]}. "
        "Prefer this over phoxtail_pages_replace_body when editing a single block."
    ),
)
def update_block(page_id: int, block_uuid: str, etag: str, value: dict[str, Any]) -> str:
    resp = request(
        "PATCH",
        f"/pages/{page_id}/blocks/{block_uuid}/",
        json_body={"value": value},
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", etag)
    return json.dumps(mark_changed_blocks(data, block_uuid), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_add_block",
    description=(
        "Add a new block to a page's StreamField body. "
        "Pass etag from a prior get call. "
        "Omit position to append; or pass position={after_uuid: '...'} / "
        "{before_uuid: '...'} / {index: N} to place it at a specific location. "
        "Available block types: use phoxtail_studio_list_blocks. "
        "Use phoxtail://schema-reference to understand each block's value shape. "
        "Creates a draft revision. Does NOT publish. "
        "Returns {block: {type, value, id}, _etag, _changed_blocks: [new_uuid]}."
    ),
)
def add_block(
    page_id: int,
    etag: str,
    type: str,
    value: dict[str, Any],
    position: dict[str, Any] | None = None,
) -> str:
    body: dict[str, Any] = {"type": type, "value": value}
    if position is not None:
        body["position"] = position
    resp = request(
        "POST",
        f"/pages/{page_id}/blocks/",
        json_body=body,
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", etag)
    return json.dumps(mark_changed_blocks(data, data.get("block", {}).get("id")), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_delete_block",
    description=(
        "Remove a block from a page's StreamField body by its UUID. "
        "Creates a draft revision. Does NOT publish. "
        "Pass etag from a prior get call. "
        "Returns {deleted_uuid: '...', _etag, _changed_blocks: [uuid]}. "
        "This action cannot be undone without re-adding the block."
    ),
)
def delete_block(page_id: int, block_uuid: str, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/pages/{page_id}/blocks/{block_uuid}/",
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", etag)
    return json.dumps(mark_changed_blocks(data, block_uuid), indent=2)


@mcp_server.tool(
    name="phoxtail_pages_move_block",
    description=(
        "Reorder a block within a page's StreamField body. "
        "Pass etag from a prior get call. "
        "position must specify exactly one of: after_uuid, before_uuid, or index. "
        "Creates a draft revision. Does NOT publish. "
        "Returns {moved_uuid: '...', _etag, _changed_blocks: [uuid]}."
    ),
)
def move_block(page_id: int, block_uuid: str, etag: str, position: dict[str, Any]) -> str:
    resp = request(
        "POST",
        f"/pages/{page_id}/blocks/{block_uuid}/move/",
        json_body={"position": position},
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", etag)
    return json.dumps(mark_changed_blocks(data, block_uuid), indent=2)
