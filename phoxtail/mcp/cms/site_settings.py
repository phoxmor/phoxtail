"""``phoxtail_site_settings_*`` MCP tools for reading and updating SiteSetting."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.cms._error import error_envelope
from phoxtail.mcp.cms._http import request


@mcp_server.tool(
    name="phoxtail_site_settings_get",
    description=(
        "Get the branding and theming settings for a Wagtail site. "
        "Auto-creates a blank SiteSetting if none exists yet. "
        "Use phoxtail_sites_list to find available site IDs. "
        "Returns image FK IDs for logo, favicon, og_image, and admin branding "
        "(null when not set). Use phoxtail_images_list to find image IDs. "
        "The response includes `_etag` which MUST be passed to "
        "phoxtail_site_settings_update for concurrency control."
    ),
)
def site_settings_get(site_id: int) -> str:
    resp = request("GET", f"/site-settings/{site_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_site_settings_update",
    description=(
        "Update branding images for a site. Pass only the image IDs you want to set — "
        "omitted fields are left untouched. "
        "To clear (unset) an image use phoxtail_site_settings_clear_image instead. "
        "Requires `etag` from a prior phoxtail_site_settings_get call. "
        "Writable fields: logo_id, logo_dark_id, favicon_id, favicon_dark_id, "
        "og_image_id, og_image_dark_id, logo_admin_id, logo_admin_dark_id, "
        "symbol_admin_id, symbol_admin_dark_id. "
        "Use phoxtail_images_list to find image IDs. "
        "Returns the updated settings with a fresh `_etag`."
    ),
)
def site_settings_update(
    site_id: int,
    etag: str,
    logo_id: int | None = None,
    logo_dark_id: int | None = None,
    favicon_id: int | None = None,
    favicon_dark_id: int | None = None,
    og_image_id: int | None = None,
    og_image_dark_id: int | None = None,
    logo_admin_id: int | None = None,
    logo_admin_dark_id: int | None = None,
    symbol_admin_id: int | None = None,
    symbol_admin_dark_id: int | None = None,
) -> str:
    fields: dict = {}
    local_vars = {
        "logo_id": logo_id,
        "logo_dark_id": logo_dark_id,
        "favicon_id": favicon_id,
        "favicon_dark_id": favicon_dark_id,
        "og_image_id": og_image_id,
        "og_image_dark_id": og_image_dark_id,
        "logo_admin_id": logo_admin_id,
        "logo_admin_dark_id": logo_admin_dark_id,
        "symbol_admin_id": symbol_admin_id,
        "symbol_admin_dark_id": symbol_admin_dark_id,
    }
    for key, value in local_vars.items():
        if value is not None:
            fields[key] = value

    resp = request(
        "PATCH",
        f"/site-settings/{site_id}/",
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
    name="phoxtail_site_settings_clear_image",
    description=(
        "Clear (set to null) one or more branding image fields on a site's settings. "
        "Requires `etag` from a prior phoxtail_site_settings_get call. "
        "Pass a comma-separated list of field names to clear, e.g. "
        "'logo_id,logo_dark_id'. Valid field names: logo_id, logo_dark_id, "
        "favicon_id, favicon_dark_id, og_image_id, og_image_dark_id, "
        "logo_admin_id, logo_admin_dark_id, symbol_admin_id, symbol_admin_dark_id. "
        "Returns the updated settings with a fresh `_etag`."
    ),
)
def site_settings_clear_image(site_id: int, etag: str, fields: str) -> str:
    valid = {
        "logo_id",
        "logo_dark_id",
        "favicon_id",
        "favicon_dark_id",
        "og_image_id",
        "og_image_dark_id",
        "logo_admin_id",
        "logo_admin_dark_id",
        "symbol_admin_id",
        "symbol_admin_dark_id",
    }
    to_clear = [f.strip() for f in fields.split(",") if f.strip()]
    unknown = [f for f in to_clear if f not in valid]
    if unknown:
        return json.dumps(
            {"error": True, "status": 400, "detail": f"Unknown fields: {unknown}"}
        )

    body = {f: None for f in to_clear}
    resp = request(
        "PATCH",
        f"/site-settings/{site_id}/",
        json_body=body,
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)
