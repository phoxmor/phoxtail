"""``phoxtail_palettes_*`` MCP tools for listing and managing Palettes."""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.design._error import error_envelope
from phoxtail.mcp.design._http import request


@mcp_server.tool(
    name="phoxtail_palettes_list",
    description=(
        "List palettes. Use `palette_set_id` to filter by set, or `search` "
        "to prefix-search by title. "
        "Each palette includes its 11 hex shades (50–950) and palette set info. "
        "Call phoxtail_palette_sets_list first to discover available sets."
    ),
)
def palettes_list(
    palette_set_id: int | None = None,
    search: str | None = None,
) -> str:
    params: dict = {}
    if palette_set_id is not None:
        params["palette_set_id"] = palette_set_id
    if search:
        params["search"] = search
    resp = request("GET", "/palettes/", params=params)
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_palettes_get",
    description=(
        "Get a single palette by id, including all 11 shade hex values. "
        "The response includes `_etag` which MUST be passed to "
        "phoxtail_palettes_update or phoxtail_palettes_delete."
    ),
)
def palettes_get(palette_id: int) -> str:
    resp = request("GET", f"/palettes/{palette_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_palettes_create",
    description=(
        "Create a new palette within a palette set. "
        "All 11 shade fields (shade_50 through shade_950) are required as "
        "hex color strings (e.g., '#3b82f6'). "
        "Use phoxtail_palette_sets_list to find valid palette_set_id values. "
        "Returns the created palette with its `_etag`."
    ),
)
def palettes_create(
    palette_set_id: int,
    title: str,
    shade_50: str,
    shade_100: str,
    shade_200: str,
    shade_300: str,
    shade_400: str,
    shade_500: str,
    shade_600: str,
    shade_700: str,
    shade_800: str,
    shade_900: str,
    shade_950: str,
    description: str = "",
    sort_order: int | None = None,
) -> str:
    body: dict = {
        "palette_set_id": palette_set_id,
        "title": title,
        "description": description,
        "shade_50": shade_50,
        "shade_100": shade_100,
        "shade_200": shade_200,
        "shade_300": shade_300,
        "shade_400": shade_400,
        "shade_500": shade_500,
        "shade_600": shade_600,
        "shade_700": shade_700,
        "shade_800": shade_800,
        "shade_900": shade_900,
        "shade_950": shade_950,
    }
    if sort_order is not None:
        body["sort_order"] = sort_order

    resp = request("POST", "/palettes/", json_body=body)
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_palettes_update",
    description=(
        "Update a palette's fields. Pass only the fields to change — "
        "omitted fields are left untouched. "
        "Requires `etag` from a prior phoxtail_palettes_get call. "
        "Writable fields: palette_set_id, title, description, sort_order, "
        "shade_50 through shade_950. "
        "Returns the updated palette with a fresh `_etag`."
    ),
)
def palettes_update(
    palette_id: int,
    etag: str,
    palette_set_id: int | None = None,
    title: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    shade_50: str | None = None,
    shade_100: str | None = None,
    shade_200: str | None = None,
    shade_300: str | None = None,
    shade_400: str | None = None,
    shade_500: str | None = None,
    shade_600: str | None = None,
    shade_700: str | None = None,
    shade_800: str | None = None,
    shade_900: str | None = None,
    shade_950: str | None = None,
) -> str:
    fields: dict = {}
    for k, v in {
        "palette_set_id": palette_set_id,
        "title": title,
        "description": description,
        "sort_order": sort_order,
        "shade_50": shade_50,
        "shade_100": shade_100,
        "shade_200": shade_200,
        "shade_300": shade_300,
        "shade_400": shade_400,
        "shade_500": shade_500,
        "shade_600": shade_600,
        "shade_700": shade_700,
        "shade_800": shade_800,
        "shade_900": shade_900,
        "shade_950": shade_950,
    }.items():
        if v is not None:
            fields[k] = v

    resp = request(
        "PATCH",
        f"/palettes/{palette_id}/",
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
    name="phoxtail_palettes_delete",
    description=(
        "Permanently delete a palette. "
        "Requires `etag` from a prior phoxtail_palettes_get call. "
        "This does NOT delete the palette set, only this one palette."
    ),
)
def palettes_delete(palette_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/palettes/{palette_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": palette_id})
