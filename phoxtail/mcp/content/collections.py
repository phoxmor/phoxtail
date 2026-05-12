"""MCP tools for Wagtail Collection CRUD.

Collections are hierarchical (tree) containers used to organise images,
documents, videos, and audio. The root node (depth=1) is included in
list results so that its id is available when creating top-level
collections or reassigning media to the root level.

Privacy (view restriction) can be read and written on every collection:
  type  "none"     — public access
        "login"    — any logged-in user
        "password" — shared password
        "groups"   — specific auth group PKs
"""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.content._http import request
from phoxtail.mcp.content.pages import _write_error_envelope


@mcp_server.tool(
    name="phoxtail_collections_list",
    description=(
        "List all collections as a flat tree (root included). "
        "Returns each collection's id, name, depth, parent_id, and view_restriction. "
        "depth=1 is the special root collection; user collections start at depth=2. "
        "A collection with parent_id matching the root id is a top-level collection. "
        "Pass a collection id as collection= when listing images/documents/videos/audio"
        " to filter media by collection."
    ),
)
def collections_list() -> str:
    resp = request("GET", "/collections/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_collections_get",
    description=(
        "Get the full detail of a single collection by id. "
        "Returns id, name, depth, parent_id, and view_restriction. "
        "The response includes `_etag` which MUST be passed back on any "
        "subsequent write call "
        "(phoxtail_collections_update, phoxtail_collections_delete) "
        "for optimistic concurrency control."
    ),
)
def collections_get(collection_id: int) -> str:
    resp = request("GET", f"/collections/{collection_id}/")
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_collections_create",
    description=(
        "Create a new collection. "
        "parent_id: the id of the parent collection. "
        "  Omit or pass null to create a top-level collection (direct child of root). "
        "  Use phoxtail_collections_list to browse existing collections. "
        "view_restriction: optional privacy settings — a dict with: "
        "  type ('none'|'password'|'login'|'groups'), "
        "  password (string, required for type=password), "
        "  groups (list of group PKs, required for type=groups). "
        "Returns the created collection including its id and an `_etag`."
    ),
)
def collections_create(
    name: str,
    parent_id: int | None = None,
    view_restriction: dict | None = None,
) -> str:
    body: dict = {"name": name}
    if parent_id is not None:
        body["parent_id"] = parent_id
    if view_restriction is not None:
        body["view_restriction"] = view_restriction
    resp = request("POST", "/collections/", json_body=body)
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_collections_update",
    description=(
        "Rename and/or reparent a collection. "
        "Requires `etag` from a prior phoxtail_collections_get call. "
        "Pass only the fields you want to change — omitted fields are left untouched. "
        "name: new name for the collection. "
        "parent_id: move the collection under a new parent. "
        "  Pass the root collection's id to make it a top-level collection. "
        "  Reparenting into a descendant of itself is refused (400). "
        "view_restriction: update privacy — dict with type, password, groups. "
        "  Pass {type: 'none'} to remove any existing restriction. "
        "Returns the updated collection with a fresh `_etag`."
    ),
)
def collections_update(
    collection_id: int,
    etag: str,
    name: str | None = None,
    parent_id: int | None = None,
    view_restriction: dict | None = None,
) -> str:
    fields: dict = {}
    if name is not None:
        fields["name"] = name
    if parent_id is not None:
        fields["parent_id"] = parent_id
    if view_restriction is not None:
        fields["view_restriction"] = view_restriction

    resp = request(
        "PATCH",
        f"/collections/{collection_id}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_collections_delete",
    description=(
        "Permanently delete a collection. "
        "Requires `etag` from a prior phoxtail_collections_get call. "
        "REFUSED (409) if the collection contains child collections or any "
        "media items (images, documents, videos, audio). "
        "You must reassign or delete all contents first before deleting the "
        "collection. "
        "The root collection (depth=1) cannot be deleted. "
        "Returns {deleted: collection_id} on success."
    ),
)
def collections_delete(collection_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/collections/{collection_id}/",
        headers={"If-Match": etag},
    )
    envelope = _write_error_envelope(resp)
    if envelope is not None:
        return envelope
    return json.dumps({"deleted": collection_id})
