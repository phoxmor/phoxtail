"""MCP tools for listing, reading, creating, updating, and deleting shared blocks."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.studio._http import get_json, request


@mcp_server.tool(
    name="phoxtail_studio_list_shared_blocks",
    description=(
        "List all shared blocks. Optionally filter by block_id, site_id, or "
        "locale_id. A shared block holds the site-scoped content for a Block "
        "that has is_shared=True — one record per (block, site, locale) triplet."
    ),
)
def list_shared_blocks(
    block_id: int | None = None,
    site_id: int | None = None,
    locale_id: int | None = None,
) -> str:
    params: dict[str, Any] = {}
    if block_id is not None:
        params["block"] = block_id
    if site_id is not None:
        params["site"] = site_id
    if locale_id is not None:
        params["locale"] = locale_id
    return json.dumps(get_json("/shared-blocks/", **params), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_get_shared_block",
    description=(
        "Get the full detail of a single shared block, including its content. "
        "Also returns the current ETag which MUST be passed to "
        "phoxtail_studio_update_shared_block for concurrency control. "
        "Pass the integer `shared_block_id` from phoxtail_studio_list_shared_blocks."
    ),
)
def get_shared_block(shared_block_id: int) -> str:
    resp = request("GET", f"/shared-blocks/{shared_block_id}/")
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_create_shared_block",
    description=(
        "Create a new shared block. Requires block_id (must have is_shared=True — "
        "use phoxtail_studio_list_blocks to find eligible blocks), site_id, and "
        "locale_id. Content is a list with exactly one entry whose block_type must "
        "match the block's identifier. Only one shared block may exist per "
        "(block, site, locale) triplet. Returns the created record with its ETag."
    ),
)
def create_shared_block(
    block_id: int,
    site_id: int,
    locale_id: int,
    content: list[dict] | None = None,
) -> str:
    body: dict[str, Any] = {
        "block_id": block_id,
        "site_id": site_id,
        "locale_id": locale_id,
    }
    if content is not None:
        body["content"] = content

    resp = request("POST", "/shared-blocks/", json_body=body)

    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "SharedBlock already exists."),
            }
        )
    if resp.status_code in (400, 404):
        return json.dumps(
            {
                "error": "validation_error" if resp.status_code == 400 else "not_found",
                "detail": resp.json().get("detail", "Invalid data."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_update_shared_block",
    description=(
        "Update a shared block's content. Requires the ETag from a prior "
        "phoxtail_studio_get_shared_block call for optimistic concurrency control. "
        "Content must be a list with exactly one entry whose block_type matches "
        "the block's identifier. The block/site/locale triplet cannot be changed. "
        "On success, returns the updated record with a new ETag."
    ),
)
def update_shared_block(
    shared_block_id: int,
    etag: str,
    content: list[dict],
) -> str:
    body: dict[str, Any] = {"content": content}

    resp = request(
        "PATCH",
        f"/shared-blocks/{shared_block_id}/",
        json_body=body,
        headers={"If-Match": etag},
    )

    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The shared block has been modified since you last read it. "
                    "Call phoxtail_studio_get_shared_block again to get the "
                    "current content and ETag, then retry."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required. Call phoxtail_studio_get_shared_block "
                    "first and pass the _etag value from the response."
                ),
            }
        )
    if resp.status_code == 400:
        return json.dumps(
            {
                "error": "validation_error",
                "detail": resp.json().get("detail", "Invalid content."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_delete_shared_block",
    description=(
        "Delete a shared block by numeric ID. This removes the site-scoped content "
        "for the (block, site, locale) triplet. The block definition itself is not "
        "affected. Pass the integer `shared_block_id` from "
        "phoxtail_studio_list_shared_blocks."
    ),
)
def delete_shared_block(shared_block_id: int) -> str:
    resp = request("DELETE", f"/shared-blocks/{shared_block_id}/")

    if resp.status_code == 404:
        return json.dumps(
            {
                "error": "not_found",
                "detail": resp.json().get(
                    "detail", f"SharedBlock {shared_block_id} not found."
                ),
            }
        )
    resp.raise_for_status()
    return json.dumps({"deleted": shared_block_id})
