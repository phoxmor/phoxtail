"""MCP tools for listing, inspecting, creating, updating, and assigning block categories.

Block categories represent the *purpose* of a block (e.g. Marketing, Ecommerce,
Application UI). Keep the vocabulary small (~5–8 broad buckets) and governed.
"""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.studio._http import get_json, request


@mcp_server.tool(
    name="phoxtail_studio_list_block_categories",
    description=(
        "List all block categories. Call this before assigning categories to a block "
        "to avoid creating duplicates. Categories represent broad purpose groupings "
        "(e.g. Marketing, Ecommerce, Application UI) — the vocabulary should stay small "
        "and governed (~5–8 buckets)."
    ),
)
def list_block_categories(search: str | None = None) -> str:
    return json.dumps(get_json("/block-categories/", search=search), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_get_block_category",
    description=(
        "Get a block category by its numeric ID. Returns the category object plus an "
        "_etag field that MUST be passed to phoxtail_studio_update_block_category for "
        "concurrency control."
    ),
)
def get_block_category(category_id: int) -> str:
    resp = request("GET", f"/block-categories/{category_id}/")
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_create_block_category",
    description=(
        "Create a new block category. Call phoxtail_studio_list_block_categories first "
        "to confirm an equivalent category does not already exist. "
        "slug must be unique and lowercase-with-hyphens. "
        "Keep the total number of categories small (~5–8 broad purpose buckets)."
    ),
)
def create_block_category(
    name: str,
    slug: str,
    description: str = "",
) -> str:
    resp = request(
        "POST",
        "/block-categories/",
        json_body={"name": name, "slug": slug, "description": description},
    )
    if resp.status_code == 409:
        return json.dumps({"error": "conflict", "detail": resp.json().get("detail", "Category already exists.")})
    if resp.status_code == 400:
        return json.dumps({"error": "validation_error", "detail": resp.json().get("detail", "Invalid data.")})
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_update_block_category",
    description=(
        "Update a block category. Requires the ETag from a prior "
        "phoxtail_studio_get_block_category call for optimistic concurrency control. "
        "Omitted fields are left untouched. Returns the updated category with a new ETag."
    ),
)
def update_block_category(
    category_id: int,
    etag: str,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
) -> str:
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if slug is not None:
        body["slug"] = slug
    if description is not None:
        body["description"] = description

    resp = request("PATCH", f"/block-categories/{category_id}/", json_body=body, headers={"If-Match": etag})
    if resp.status_code == 409:
        return json.dumps({"error": "conflict", "detail": resp.json().get("detail", "Slug already exists.")})
    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The category has been modified since you last read it. "
                    "Call phoxtail_studio_get_block_category again to get the "
                    "current content and ETag, then retry."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required. Call phoxtail_studio_get_block_category "
                    "first and pass the _etag value from the response."
                ),
            }
        )
    if resp.status_code == 400:
        return json.dumps({"error": "validation_error", "detail": resp.json().get("detail", "Invalid data.")})
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_delete_block_category",
    description="Delete a block category by its numeric ID.",
)
def delete_block_category(category_id: int) -> str:
    resp = request("DELETE", f"/block-categories/{category_id}/")
    resp.raise_for_status()
    return json.dumps({"deleted": category_id})


@mcp_server.tool(
    name="phoxtail_studio_set_block_categories",
    description=(
        "Replace the full set of categories assigned to a block. "
        "Pass a list of category IDs — existing assignments not in the list will be removed. "
        "Call phoxtail_studio_list_block_categories first to get valid IDs."
    ),
)
def set_block_categories(block_id: int, category_ids: list[int]) -> str:
    resp = request("PUT", f"/blocks/{block_id}/categories/", json_body={"category_ids": category_ids})
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_add_block_category",
    description=(
        "Add a single category to a block. Returns 409 if the category is already assigned. "
        "Call phoxtail_studio_list_block_categories first to get a valid category_id."
    ),
)
def add_block_category(block_id: int, category_id: int) -> str:
    resp = request("POST", f"/blocks/{block_id}/categories/{category_id}/")
    if resp.status_code == 409:
        return json.dumps({"error": "conflict", "detail": resp.json().get("detail", "Already assigned.")})
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_remove_block_category",
    description="Remove a single category from a block. Returns 404 if the category is not currently assigned.",
)
def remove_block_category(block_id: int, category_id: int) -> str:
    resp = request("DELETE", f"/blocks/{block_id}/categories/{category_id}/")
    resp.raise_for_status()
    return json.dumps({"removed": {"block_id": block_id, "category_id": category_id}})
