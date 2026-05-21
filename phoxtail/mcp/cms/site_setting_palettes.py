"""``phoxtail_site_setting_palettes_*`` MCP tools for managing SiteSettingPalette."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.cms._error import error_envelope
from phoxtail.mcp.cms._http import request


@mcp_server.tool(
    name="phoxtail_site_setting_palettes_list",
    description=(
        "List palette assignments for a site. "
        "Each assignment maps a Palette to a semantic PaletteRole "
        "(e.g., surface, primary, accent). "
        "Use phoxtail_sites_list to find available site IDs. "
        "Returns id, palette_id, palette_title, role_id, role_name, "
        "role_identifier, and sort_order for each assignment."
    ),
)
def site_setting_palettes_list(site_id: int) -> str:
    resp = request("GET", f"/site-settings/{site_id}/palettes/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_site_setting_palettes_get",
    description=(
        "Get a single palette assignment by id. "
        "Use phoxtail_site_setting_palettes_list to find assignment IDs. "
        "The response includes `_etag` which MUST be passed to "
        "phoxtail_site_setting_palettes_update or "
        "phoxtail_site_setting_palettes_remove."
    ),
)
def site_setting_palettes_get(site_id: int, palette_id: int) -> str:
    resp = request("GET", f"/site-settings/{site_id}/palettes/{palette_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_site_setting_palettes_add",
    description=(
        "Assign a palette to a semantic role on a site. "
        "Use phoxtail_palettes_list to find palette_id values. "
        "Use phoxtail_palette_roles_list to find role_id values. "
        "Each role can only be assigned once per site — adding a duplicate role "
        "returns a conflict error. "
        "sort_order controls display ordering (lower = first); omit to auto-append at the end. "
        "Returns the created assignment including its `_etag`."
    ),
)
def site_setting_palettes_add(
    site_id: int,
    palette_id: int,
    role_id: int,
    sort_order: int | None = None,
) -> str:
    body: dict = {"palette_id": palette_id, "role_id": role_id}
    if sort_order is not None:
        body["sort_order"] = sort_order
    resp = request(
        "POST",
        f"/site-settings/{site_id}/palettes/",
        json_body=body,
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_site_setting_palettes_update",
    description=(
        "Update a palette assignment. Pass only the fields you want to change — "
        "omitted fields are left untouched. "
        "Requires `etag` from a prior phoxtail_site_setting_palettes_get call. "
        "Writable fields: new_palette_id (to change the palette), role_id, sort_order. "
        "Changing role_id fails with a conflict error if that role is already "
        "assigned on the site. "
        "Returns the updated assignment with a fresh `_etag`."
    ),
)
def site_setting_palettes_update(
    site_id: int,
    palette_id: int,
    etag: str,
    new_palette_id: int | None = None,
    role_id: int | None = None,
    sort_order: int | None = None,
) -> str:
    fields: dict = {}
    if new_palette_id is not None:
        fields["palette_id"] = new_palette_id
    if role_id is not None:
        fields["role_id"] = role_id
    if sort_order is not None:
        fields["sort_order"] = sort_order

    resp = request(
        "PATCH",
        f"/site-settings/{site_id}/palettes/{palette_id}/",
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
    name="phoxtail_site_setting_palettes_remove",
    description=(
        "Remove a palette assignment from a site. "
        "Requires `etag` from a prior phoxtail_site_setting_palettes_get call. "
        "The Palette itself is not deleted — only the site assignment is removed."
    ),
)
def site_setting_palettes_remove(site_id: int, palette_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/site-settings/{site_id}/palettes/{palette_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"removed": palette_id, "site_id": site_id})
