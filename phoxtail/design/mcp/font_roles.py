"""``phoxtail_font_roles_*`` MCP tools for font role management."""

from __future__ import annotations

import json

from phoxtail.design.mcp._error import error_envelope
from phoxtail.design.mcp._http import request
from phoxtail.mcp import mcp_server


@mcp_server.tool(
    name="phoxtail_font_roles_list",
    description=(
        "List all semantic font roles in the design system "
        "(e.g., 'heading', 'body', 'monospace'). "
        "Roles define how font families map to CSS variable namespaces "
        "like --font-{identifier}-*. "
        "Read these before assigning fonts to understand design system semantics."
    ),
)
def font_roles_list(search: str | None = None) -> str:
    params = {}
    if search:
        params["search"] = search
    resp = request("GET", "/font-roles/", params=params)
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_font_roles_get",
    description=(
        "Get a single font role by id. "
        "Returns id, name, identifier, and description. "
        "Response includes `_etag` for write operations."
    ),
)
def font_roles_get(role_id: int) -> str:
    resp = request("GET", f"/font-roles/{role_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_font_roles_create",
    description=(
        "Create a new semantic font role. "
        "`identifier` becomes the CSS namespace (e.g., 'heading' → "
        "--font-heading-*). "
        "`description` should explain where this role is used typographically."
    ),
)
def font_roles_create(
    name: str,
    identifier: str,
    description: str = "",
) -> str:
    resp = request(
        "POST",
        "/font-roles/",
        json_body={"name": name, "identifier": identifier, "description": description},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_font_roles_update",
    description=(
        "Update a font role. Requires `etag` from phoxtail_font_roles_get. "
        "WARNING: changing `identifier` renames the CSS variable namespace — "
        "update any template references too."
    ),
)
def font_roles_update(
    role_id: int,
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
        f"/font-roles/{role_id}/",
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
    name="phoxtail_font_roles_delete",
    description=(
        "Delete a font role. Requires `etag` from phoxtail_font_roles_get. "
        "WARNING: this removes a CSS variable namespace from the design system — "
        "verify no templates reference this role before deleting."
    ),
)
def font_roles_delete(role_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/font-roles/{role_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": role_id})
