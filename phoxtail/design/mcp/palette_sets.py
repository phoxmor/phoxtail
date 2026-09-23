"""``phoxtail_palette_sets_*`` MCP tools for listing and managing PaletteSets."""

from __future__ import annotations

import json

from phoxtail.design.mcp._error import error_envelope
from phoxtail.design.mcp._http import request
from phoxtail.mcp import mcp_server
from phoxtail.mcp.authorization import scoped
from phoxtail.mcp.pagination import DEFAULT_LIMIT, PAGED, Limit, Offset


@mcp_server.tool(
    name="phoxtail_palette_sets_list",
    auth=[scoped("phoxtail_design.view_paletteset")],
    description=(
        "List palette sets in the project. "
        "A palette set groups related palettes under a shared concept "
        "(e.g., 'tailwind', 'spring', 'autumn'). "
        "Returns id, name, identifier, description, and palette_count for each set. " + PAGED
    ),
)
def palette_sets_list(search: str | None = None, limit: Limit = DEFAULT_LIMIT, offset: Offset = 0) -> str:
    params: dict = {"limit": limit, "offset": offset}
    if search:
        params["search"] = search
    resp = request("GET", "/palette-sets/", params=params)
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_palette_sets_get",
    auth=[scoped("phoxtail_design.view_paletteset")],
    description=(
        "Get a single palette set by id. "
        "The response includes `_etag` which MUST be passed to "
        "phoxtail_palette_sets_update or phoxtail_palette_sets_delete."
    ),
)
def palette_sets_get(palette_set_id: int) -> str:
    resp = request("GET", f"/palette-sets/{palette_set_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_palette_sets_create",
    auth=[scoped("phoxtail_design.add_paletteset")],
    description=(
        "Create a new palette set. "
        "`name` is the human-readable label (e.g., 'Tailwind'). "
        "`identifier` is a slug matching the filesystem group directory "
        "(e.g., 'tailwind'). "
        "Returns the created palette set including its `_etag`."
    ),
)
def palette_sets_create(
    name: str,
    identifier: str,
    description: str = "",
) -> str:
    resp = request(
        "POST",
        "/palette-sets/",
        json_body={"name": name, "identifier": identifier, "description": description},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_palette_sets_update",
    auth=[scoped("phoxtail_design.change_paletteset")],
    description=(
        "Update a palette set's fields. Pass only the fields to change — "
        "omitted fields are left untouched. "
        "Requires `etag` from a prior phoxtail_palette_sets_get call. "
        "Writable fields: name, identifier, description. "
        "Returns the updated palette set with a fresh `_etag`."
    ),
)
def palette_sets_update(
    palette_set_id: int,
    etag: str,
    name: str | None = None,
    identifier: str | None = None,
    description: str | None = None,
) -> str:
    fields: dict = {}
    if name is not None:
        fields["name"] = name
    if identifier is not None:
        fields["identifier"] = identifier
    if description is not None:
        fields["description"] = description

    resp = request(
        "PATCH",
        f"/palette-sets/{palette_set_id}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_palette_sets_delete",
    auth=[scoped("phoxtail_design.delete_paletteset")],
    description=(
        "Permanently delete a palette set and all its palettes. "
        "Requires `etag` from a prior phoxtail_palette_sets_get call. "
        "WARNING: this cascades — all palettes in the set are deleted too."
    ),
)
def palette_sets_delete(palette_set_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/palette-sets/{palette_set_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": palette_set_id})
