"""MCP tools for listing, inspecting, creating, and updating variant collections."""

from __future__ import annotations

import json
from typing import Any

from phoxtail.api.schemas import NonBlank
from phoxtail.mcp import mcp_server
from phoxtail.mcp.authorization import scoped
from phoxtail.mcp.pagination import DEFAULT_LIMIT, PAGED, Limit, Offset
from phoxtail.streams.mcp._http import get_json, request


@mcp_server.tool(
    name="phoxtail_studio_list_collections",
    auth=[scoped("phoxtail_streams.view_variantcollection")],
    description=(
        "List the variant collections in the project. "
        "A collection groups variants under a shared design system "
        "(e.g. 'general-unsorted', 'material-design-3'). " + PAGED
    ),
)
def list_collections(search: str | None = None, limit: Limit = DEFAULT_LIMIT, offset: Offset = 0) -> str:
    return json.dumps(get_json("/collections/", search=search, limit=limit, offset=offset), indent=2)


@mcp_server.tool(
    name="phoxtail_studio_get_collection",
    auth=[scoped("phoxtail_streams.view_variantcollection")],
    description=(
        "Get a collection's full detail — name, identifier, and description. "
        "Also returns the current ETag which MUST be passed to "
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
    auth=[scoped("phoxtail_streams.add_variantcollection")],
    description=(
        "Create a new variant collection — an optional ad-hoc design-system "
        "label that variants can belong to (e.g. 'Material Design 3', 'HIG'). "
        "Requires an identifier (unique, lowercase_with_underscores), a "
        "human-readable name and a description. Returns the created collection with its ETag."
    ),
)
def create_collection(
    identifier: NonBlank,
    name: NonBlank,
    description: NonBlank,
) -> str:
    resp = request(
        "POST",
        "/collections/",
        json_body={
            "identifier": identifier,
            "name": name,
            "description": description,
        },
    )
    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "Collection already exists."),
            }
        )
    if resp.status_code in (400, 422):
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
    auth=[scoped("phoxtail_streams.change_variantcollection")],
    description=(
        "Update a collection's metadata. "
        "Requires the ETag from a prior phoxtail_studio_get_collection call "
        "for optimistic concurrency control — if the collection has been "
        "modified since you read it, the update will fail with a conflict "
        "error. Omitted fields are left untouched. "
        "identifier must be unique (lowercase_with_underscores); a 409 is "
        "returned if it clashes with an existing collection. "
        "On success, returns the updated collection with a new ETag."
    ),
)
def update_collection(
    collection_id: int,
    etag: str,
    identifier: NonBlank | None = None,
    name: NonBlank | None = None,
    description: NonBlank | None = None,
) -> str:
    body: dict[str, Any] = {}
    if identifier is not None:
        body["identifier"] = identifier
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description

    resp = request(
        "PATCH",
        f"/collections/{collection_id}/",
        json_body=body,
        headers={"If-Match": etag},
    )
    if resp.status_code == 409:
        return json.dumps(
            {
                "error": "conflict",
                "detail": resp.json().get("detail", "A collection with this identifier or name already exists."),
            }
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
    if resp.status_code in (400, 422):
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
    name="phoxtail_studio_delete_collection",
    auth=[scoped("phoxtail_streams.delete_variantcollection")],
    description=(
        "Permanently delete a variant collection by its numeric ID. "
        "WARNING: variants that belong to this collection will have their "
        "collection field set to null. This action cannot be undone. "
        "Pass the integer `collection_id` from phoxtail_studio_list_collections."
    ),
)
def delete_collection(collection_id: int) -> str:
    resp = request("DELETE", f"/collections/{collection_id}/")
    if resp.status_code == 404:
        return json.dumps({"error": "not_found", "detail": f"Collection {collection_id} not found."})
    resp.raise_for_status()
    return json.dumps({"deleted": True, "collection_id": collection_id})
