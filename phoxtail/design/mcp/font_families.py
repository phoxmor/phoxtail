"""``phoxtail_font_families_*`` MCP tools for font family management."""

from __future__ import annotations

import json

from phoxtail.design.mcp._error import error_envelope
from phoxtail.design.mcp._http import request
from phoxtail.mcp import mcp_server

_CATEGORIES = "serif, sans-serif, monospace, display, handwriting"


@mcp_server.tool(
    name="phoxtail_font_families_list",
    description=(
        "List all font families in the design system. "
        "Use `category` to filter (choices: " + _CATEGORIES + "). "
        "Returns id, name, category, fallback CSS, weight_count."
    ),
)
def font_families_list(
    search: str | None = None,
    category: str | None = None,
) -> str:
    params: dict = {}
    if search:
        params["search"] = search
    if category:
        params["category"] = category
    resp = request("GET", "/font-families/", params=params)
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_font_families_get",
    description=(
        "Get a single font family by id. "
        "Returns id, name, description, category, fallback, weight_count. "
        "Response includes `_etag` for write operations."
    ),
)
def font_families_get(font_family_id: int) -> str:
    resp = request("GET", f"/font-families/{font_family_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_font_families_create",
    description=(
        "Create a new font family entry. "
        "category choices: " + _CATEGORIES + ". "
        "`fallback` is the CSS fallback stack (e.g., 'system-ui, sans-serif'). "
        "Font weight files are uploaded separately via phoxtail_font_weights_upload."
    ),
)
def font_families_create(
    name: str,
    description: str = "",
    category: str = "sans-serif",
    fallback: str = "system-ui, -apple-system, sans-serif",
) -> str:
    resp = request(
        "POST",
        "/font-families/",
        json_body={
            "name": name,
            "description": description,
            "category": category,
            "fallback": fallback,
        },
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_font_families_update",
    description=(
        "Update a font family's metadata. "
        "Requires `etag` from phoxtail_font_families_get. "
        "Writable fields: name, description, category, fallback."
    ),
)
def font_families_update(
    font_family_id: int,
    etag: str,
    name: str | None = None,
    description: str | None = None,
    category: str | None = None,
    fallback: str | None = None,
) -> str:
    fields: dict = {}
    if name is not None:
        fields["name"] = name
    if description is not None:
        fields["description"] = description
    if category is not None:
        fields["category"] = category
    if fallback is not None:
        fields["fallback"] = fallback

    resp = request(
        "PATCH",
        f"/font-families/{font_family_id}/",
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
    name="phoxtail_font_families_delete",
    description=(
        "Delete a font family and all its weight entries. "
        "Requires `etag` from phoxtail_font_families_get. "
        "WARNING: this cascades — all font weight files are deleted too."
    ),
)
def font_families_delete(font_family_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/font-families/{font_family_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": font_family_id})
