"""``phoxtail_site_setting_fonts_*`` MCP tools for managing SiteSettingFont."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.cms._error import error_envelope
from phoxtail.mcp.cms._http import request


@mcp_server.tool(
    name="phoxtail_site_setting_fonts_list",
    description=(
        "List font assignments for a site. "
        "Each assignment maps a FontFamily to a semantic FontRole "
        "(e.g., heading, body, mono). "
        "Use phoxtail_sites_list to find available site IDs. "
        "Returns id, font_family_id, font_family_name, role_id, role_name, "
        "role_identifier, and sort_order for each assignment."
    ),
)
def site_setting_fonts_list(site_id: int) -> str:
    resp = request("GET", f"/site-settings/{site_id}/fonts/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_site_setting_fonts_get",
    description=(
        "Get a single font assignment by id. "
        "Use phoxtail_site_setting_fonts_list to find assignment IDs. "
        "The response includes `_etag` which MUST be passed to "
        "phoxtail_site_setting_fonts_update or phoxtail_site_setting_fonts_remove."
    ),
)
def site_setting_fonts_get(site_id: int, font_id: int) -> str:
    resp = request("GET", f"/site-settings/{site_id}/fonts/{font_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_site_setting_fonts_add",
    description=(
        "Assign a font family to a semantic role on a site. "
        "Use phoxtail_font_families_list to find font_family_id values. "
        "Use phoxtail_font_roles_list to find role_id values. "
        "Each role can only be assigned once per site — adding a duplicate role "
        "returns a conflict error. "
        "sort_order controls display ordering (lower = first); omit to auto-append at the end. "
        "Returns the created assignment including its `_etag`."
    ),
)
def site_setting_fonts_add(
    site_id: int,
    font_family_id: int,
    role_id: int,
    sort_order: int | None = None,
) -> str:
    body: dict = {"font_family_id": font_family_id, "role_id": role_id}
    if sort_order is not None:
        body["sort_order"] = sort_order
    resp = request(
        "POST",
        f"/site-settings/{site_id}/fonts/",
        json_body=body,
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_site_setting_fonts_update",
    description=(
        "Update a font assignment. Pass only the fields you want to change — "
        "omitted fields are left untouched. "
        "Requires `etag` from a prior phoxtail_site_setting_fonts_get call. "
        "Writable fields: font_family_id, role_id, sort_order. "
        "Changing role_id fails with a conflict error if that role is already "
        "assigned on the site. "
        "Returns the updated assignment with a fresh `_etag`."
    ),
)
def site_setting_fonts_update(
    site_id: int,
    font_id: int,
    etag: str,
    font_family_id: int | None = None,
    role_id: int | None = None,
    sort_order: int | None = None,
) -> str:
    fields: dict = {}
    if font_family_id is not None:
        fields["font_family_id"] = font_family_id
    if role_id is not None:
        fields["role_id"] = role_id
    if sort_order is not None:
        fields["sort_order"] = sort_order

    resp = request(
        "PATCH",
        f"/site-settings/{site_id}/fonts/{font_id}/",
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
    name="phoxtail_site_setting_fonts_remove",
    description=(
        "Remove a font assignment from a site. "
        "Requires `etag` from a prior phoxtail_site_setting_fonts_get call. "
        "The FontFamily itself is not deleted — only the site assignment is removed."
    ),
)
def site_setting_fonts_remove(site_id: int, font_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/site-settings/{site_id}/fonts/{font_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"removed": font_id, "site_id": site_id})
