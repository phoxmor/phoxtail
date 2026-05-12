"""MCP tools for listing, reading, diffing, updating, and creating variants."""

from __future__ import annotations

import difflib
import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.studio._http import get_json, request

# -- Listing ---------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_list_variants",
    description=(
        "List all block variants in the project. "
        "Optionally filter by block identifier and/or collection identifier. "
        "Returns a summary of each variant: id (integer), identifier (string), "
        "name, description, block, collection, is_default. "
        "IMPORTANT: when adding a block to a page body, the `variant` field "
        "must be the integer `id`, NOT the string `identifier`."
    ),
)
def list_variants(
    block: str | None = None,
    collection: str | None = None,
    search: str | None = None,
) -> str:
    data = get_json("/variants/", block=block, collection=collection, search=search)
    return json.dumps(data, indent=2)


# -- Read ------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_get_variant",
    description=(
        "Get the full detail of a single block variant, including its HTML, "
        "CSS, and JavaScript content. Also returns the current ETag which "
        "MUST be passed to phoxtail_studio_update_variant for concurrency "
        "control. Pass the integer `variant_id` from phoxtail_studio_list_variants. "
        "NOTE: for editing use phoxtail_studio_open_variant instead — it writes "
        "the content to local files so you can use Edit for surgical changes "
        "without reloading the full payload on every turn."
    ),
)
def get_variant(variant_id: int) -> str:
    resp = request("GET", f"/variants/{variant_id}/")
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


# -- Diff ------------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_diff_variant",
    description=(
        "Show a unified diff between a variant's current content in the "
        "database and proposed new content. Pass the fields you intend to "
        "change (identifier, name, description, html, css, javascript); "
        "omitted fields are not diffed. "
        "Use this to preview changes before calling "
        "phoxtail_studio_update_variant."
    ),
)
def diff_variant(
    variant_id: int,
    identifier: str | None = None,
    name: str | None = None,
    description: str | None = None,
    html: str | None = None,
    css: str | None = None,
    javascript: str | None = None,
) -> str:
    resp = request("GET", f"/variants/{variant_id}/")
    resp.raise_for_status()
    current = resp.json()

    parts: list[str] = []
    for field, new_value in [
        ("identifier", identifier),
        ("name", name),
        ("description", description),
        ("html", html),
        ("css", css),
        ("javascript", javascript),
    ]:
        if new_value is None:
            continue
        old_lines = current[field].splitlines(keepends=True)
        new_lines = new_value.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{field}",
            tofile=f"b/{field}",
        )
        parts.append("".join(diff))

    result = "\n".join(p for p in parts if p)
    return result or "(no differences)"


# -- Write -----------------------------------------------------------------


@mcp_server.tool(
    name="phoxtail_studio_update_variant",
    description=(
        "Update any mutable field on a variant: identifier, name, description, "
        "collection_id (move to a different design system collection), "
        "preview_image_id (set or clear the preview screenshot), "
        "is_default (atomically demotes any existing default on the same block), "
        "and content fields html, css, javascript. "
        "Pass the `variant_id` and the ETag from a prior "
        "phoxtail_studio_get_variant call for optimistic concurrency control "
        "— if the variant has been modified since you read it, the update "
        "will fail with a conflict error. Omitted fields are left untouched. "
        "WARNING: renaming `identifier` will look like a delete+create on the "
        "next studio dump/sync because the filesystem path is keyed on it. "
        "On success, returns the updated variant with a new ETag. "
        "NOTE: for surgical edits (changing specific lines rather than "
        "rewriting entire fields) prefer phoxtail_studio_open_variant + "
        "filesystem Edit + phoxtail_studio_commit_variant — this route only "
        "sends the changed lines and shows diffs before each write."
    ),
)
def update_variant(
    variant_id: int,
    etag: str,
    identifier: str | None = None,
    name: str | None = None,
    description: str | None = None,
    collection_id: int | None = None,
    preview_image_id: int | None = None,
    html: str | None = None,
    css: str | None = None,
    javascript: str | None = None,
    is_default: bool | None = None,
) -> str:
    body: dict[str, Any] = {}
    if identifier is not None:
        body["identifier"] = identifier
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if collection_id is not None:
        body["collection_id"] = collection_id
    if preview_image_id is not None:
        body["preview_image_id"] = preview_image_id
    if html is not None:
        body["html"] = html
    if css is not None:
        body["css"] = css
    if javascript is not None:
        body["javascript"] = javascript
    if is_default is not None:
        body["is_default"] = is_default

    resp = request(
        "PUT",
        f"/variants/{variant_id}/",
        json_body=body,
        headers={"If-Match": etag},
    )
    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The variant has been modified since you last read it. "
                    "Call phoxtail_studio_get_variant again to get the "
                    "current content and ETag, then retry."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required. Call phoxtail_studio_get_variant "
                    "first and pass the _etag value from the response."
                ),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_create_variant",
    description=(
        "Create a new block variant. Requires an identifier (unique within "
        "the block+collection pair), a human-readable name, and the numeric "
        "IDs of an existing block and collection. Pass `block_id` from "
        "phoxtail_studio_list_blocks and `collection_id` from "
        "phoxtail_studio_list_collections. "
        "Content fields (html, css, javascript) default to empty strings. "
        "Set is_default=true to mark as the block's default variant "
        "(only one default per block is allowed). "
        "Returns the created variant with its ETag."
    ),
)
def create_variant(
    identifier: str,
    name: str,
    block_id: int,
    collection_id: int,
    description: str = "",
    html: str = "",
    css: str = "",
    javascript: str = "",
    is_default: bool = False,
) -> str:
    resp = request(
        "POST",
        "/variants/",
        json_body={
            "identifier": identifier,
            "name": name,
            "block_id": block_id,
            "collection_id": collection_id,
            "description": description,
            "html": html,
            "css": css,
            "javascript": javascript,
            "is_default": is_default,
        },
    )
    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "Variant already exists."),
            }
        )
    if resp.status_code == 404:
        return json.dumps(
            {
                "error": "not_found",
                "detail": resp.json().get("detail", "Block or collection not found."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)
