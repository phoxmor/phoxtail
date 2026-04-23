"""MCP tools for listing, inspecting, creating, and updating variant collections."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.mcp.studio._http import get_json, request


@mcp_server.tool(
    name="phoxtail_studio_list_collections",
    description=(
        "List all variant collections in the project. "
        "A collection groups variants under a shared design system "
        "(e.g. 'ground-state', 'material-design')."
    ),
)
def list_collections(search: str | None = None) -> str:
    return json.dumps(get_json("/collections/", search=search), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_get_collection",
    description=(
        "Get a collection's full detail including its design guidelines "
        "(the template field) — the philosophy, principles, and design "
        "patterns that define this collection's character. Also returns "
        "the current ETag which MUST be passed to "
        "phoxtail_studio_update_collection for concurrency control. "
        "Pass the integer `collection_id` from phoxtail_studio_list_collections. "
        "Design tokens (palette roles, font roles) are provided "
        "separately via the context tool."
    ),
)
def get_collection(collection_id: int) -> str:
    resp = request("GET", f"/collections/{collection_id}/")
    resp.raise_for_status()
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_create_collection",
    description=(
        "Create a new variant collection — a named design system that "
        "variants can belong to. Requires an identifier "
        "(unique, lowercase_with_underscores) and a human-readable name. "
        "The template field should contain a Markdown document describing "
        "the collection's design philosophy, principles, and guidelines "
        "that agents will use when creating variants for this collection. "
        "Returns the created collection with its ETag."
    ),
)
def create_collection(
    identifier: str,
    name: str,
    description: str = "",
    template: str = "",
) -> str:
    resp = request(
        "POST",
        "/collections/",
        json_body={
            "identifier": identifier,
            "name": name,
            "description": description,
            "template": template,
        },
    )
    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "Collection already exists."),
            }
        )
    if resp.status_code == 400:
        return json.dumps(
            {
                "error": "validation_error",
                "detail": resp.json().get("detail", "Invalid collection data."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_studio_update_collection",
    description=(
        "Update a collection's metadata and/or design guidelines template. "
        "Requires the ETag from a prior phoxtail_studio_get_collection call "
        "for optimistic concurrency control — if the collection has been "
        "modified since you read it, the update will fail with a conflict "
        "error. Omitted fields are left untouched. "
        "On success, returns the updated collection with a new ETag."
    ),
)
def update_collection(
    collection_id: int,
    etag: str,
    name: str | None = None,
    description: str | None = None,
    template: str | None = None,
) -> str:
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if template is not None:
        body["template"] = template

    resp = request(
        "PATCH",
        f"/collections/{collection_id}/",
        json_body=body,
        headers={"If-Match": etag},
    )
    if resp.status_code == 412:
        return json.dumps(
            {
                "error": "conflict",
                "detail": (
                    "The collection has been modified since you last read it. "
                    "Call phoxtail_studio_get_collection again to get the "
                    "current content and ETag, then retry."
                ),
            }
        )
    if resp.status_code == 428:
        return json.dumps(
            {
                "error": "precondition_required",
                "detail": (
                    "ETag is required. Call phoxtail_studio_get_collection "
                    "first and pass the _etag value from the response."
                ),
            }
        )
    if resp.status_code == 400:
        return json.dumps(
            {
                "error": "validation_error",
                "detail": resp.json().get("detail", "Invalid collection data."),
            }
        )
    resp.raise_for_status()

    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)
