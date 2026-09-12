"""MCP tools for listing, reading, creating, and updating blocks."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.streams.mcp._http import get_json, request


@mcp_server.tool(
    name="phoxtail_studio_list_blocks",
    description=(
        "List all blocks in the project. "
        "A block is a structural schema (e.g. 'header_section', 'hero') "
        "that variants implement."
    ),
)
def list_blocks(search: str | None = None) -> str:
    return json.dumps(get_json("/blocks/", search=search), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_get_block",
    description=(
        "Get the full detail of a single block, including its field schema, "
        "page types, variants, and metadata. Also returns the current ETag "
        "which MUST be passed to phoxtail_studio_update_block for "
        "concurrency control. Pass the integer `block_id` from "
        "phoxtail_studio_list_blocks."
    ),
)
def get_block(block_id: int) -> str:
    resp = request("GET", f"/blocks/{block_id}/")
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_create_block",
    description=(
        "Create a new block with its field schema. Requires an identifier "
        "(unique, lowercase_with_underscores), a human-readable name, and "
        "the schema definition as a list of field objects. "
        "Use the phoxtail://schema-reference resource to see available "
        "field types and their parameters. "
        "A shared block may also declare `site_slot` (head_start, head_end, "
        "body_start, before_content, after_content, body_end) to render "
        "automatically at that position on every page of a site that fills "
        "in its shared content; `slot_order` orders blocks within the same "
        "slot and `render_in_preview=False` keeps it out of previews and "
        "screenshots (use for analytics/tracking scripts). "
        "Returns the created block with its ETag."
    ),
)
def create_block(
    identifier: str,
    name: str,
    description: str = "",
    icon: str = "",
    group: str = "",
    is_shared: bool = False,
    site_slot: str = "",
    slot_order: int = 0,
    render_in_preview: bool = True,
    sort_order: int | None = None,
    page_types: list[str] | None = None,
    schema: list[dict] | None = None,
) -> str:
    body: dict[str, Any] = {
        "identifier": identifier,
        "name": name,
        "description": description,
        "icon": icon,
        "group": group,
        "is_shared": is_shared,
        "site_slot": site_slot,
        "slot_order": slot_order,
        "render_in_preview": render_in_preview,
    }
    if sort_order is not None:
        body["sort_order"] = sort_order
    if page_types is not None:
        body["page_types"] = page_types
    if schema is not None:
        body["schema"] = schema

    resp = request("POST", "/blocks/", json_body=body)

    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "Block already exists."),
            }
        )
    if resp.status_code == 400:
        return json.dumps(
            {
                "error": "validation_error",
                "detail": resp.json().get("detail", "Invalid block data."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_update_block",
    description=(
        "Update any mutable field on a block: identifier, name, description, "
        "icon, group, is_shared, site_slot, slot_order, render_in_preview, "
        "sort_order, page_types, and schema. "
        "Requires the ETag from a prior phoxtail_studio_get_block call "
        "for optimistic concurrency control. Omitted fields are left "
        "untouched. "
        "WARNING: renaming `identifier` will look like a delete+create on the "
        "next studio dump/sync because filesystem paths are keyed on it. "
        "WARNING: changing the schema may break existing variants' templates "
        "that reference removed or renamed fields. "
        "On success, returns the updated block with a new ETag."
    ),
)
def update_block(
    block_id: int,
    etag: str,
    identifier: str | None = None,
    name: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    group: str | None = None,
    is_shared: bool | None = None,
    site_slot: str | None = None,
    slot_order: int | None = None,
    render_in_preview: bool | None = None,
    sort_order: int | None = None,
    page_types: list[str] | None = None,
    schema: list[dict] | None = None,
) -> str:
    body: dict[str, Any] = {}
    if identifier is not None:
        body["identifier"] = identifier
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if icon is not None:
        body["icon"] = icon
    if group is not None:
        body["group"] = group
    if is_shared is not None:
        body["is_shared"] = is_shared
    if site_slot is not None:
        body["site_slot"] = site_slot
    if slot_order is not None:
        body["slot_order"] = slot_order
    if render_in_preview is not None:
        body["render_in_preview"] = render_in_preview
    if sort_order is not None:
        body["sort_order"] = sort_order
    if page_types is not None:
        body["page_types"] = page_types
    if schema is not None:
        body["schema"] = schema

    resp = request(
        "PATCH",
        f"/blocks/{block_id}/",
        json_body=body,
        headers={"If-Match": etag},
    )

    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "Identifier already exists."),
            }
        )
    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The block has been modified since you last read it. "
                    "Call phoxtail_studio_get_block again to get the "
                    "current content and ETag, then retry."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required. Call phoxtail_studio_get_block first and pass the _etag value from the response."
                ),
            }
        )
    if resp.status_code == 400:
        return json.dumps(
            {
                "error": "validation_error",
                "detail": resp.json().get("detail", "Invalid block data."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_delete_block",
    description=(
        "Permanently delete a block by its numeric ID. "
        "WARNING: this also deletes all variants belonging to the block. "
        "This action cannot be undone. "
        "Pass the integer `block_id` from phoxtail_studio_list_blocks."
    ),
)
def delete_block(block_id: int) -> str:
    resp = request("DELETE", f"/blocks/{block_id}/")
    if resp.status_code == 404:
        return json.dumps({"error": "not_found", "detail": f"Block {block_id} not found."})
    resp.raise_for_status()
    return json.dumps({"deleted": True, "block_id": block_id})
