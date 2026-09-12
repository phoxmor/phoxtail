"""``phoxtail_palette_roles_*`` MCP tools for palette role management."""

from __future__ import annotations

import json

from phoxtail.design.mcp._error import error_envelope
from phoxtail.design.mcp._http import request
from phoxtail.mcp import mcp_server


@mcp_server.tool(
    name="phoxtail_palette_roles_list",
    description=(
        "List all semantic palette roles in the design system "
        "(e.g., 'primary', 'surface', 'accent'). "
        "Roles define how palettes map to CSS variable namespaces "
        "like --color-{identifier}-{shade}. "
        "Read these before creating palettes to understand the design system semantics."
    ),
)
def palette_roles_list(search: str | None = None) -> str:
    params = {}
    if search:
        params["search"] = search
    resp = request("GET", "/palette-roles/", params=params)
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_palette_roles_get",
    description=(
        "Get a single palette role by id. "
        "Returns id, name, identifier, and description. "
        "The response includes `_etag` for write operations."
    ),
)
def palette_roles_get(role_id: int) -> str:
    resp = request("GET", f"/palette-roles/{role_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_palette_roles_create",
    description=(
        "Create a new semantic palette role. "
        "`identifier` is the CSS namespace key (e.g., 'primary' → "
        "--color-primary-500). "
        "`description` should explain light/dark mode shade mapping semantics."
    ),
)
def palette_roles_create(
    name: str,
    identifier: str,
    description: str = "",
) -> str:
    resp = request(
        "POST",
        "/palette-roles/",
        json_body={"name": name, "identifier": identifier, "description": description},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_palette_roles_update",
    description=(
        "Update a palette role. Requires `etag` from phoxtail_palette_roles_get. "
        "WARNING: changing `identifier` renames the CSS variable namespace — "
        "update any template references too."
    ),
)
def palette_roles_update(
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
        f"/palette-roles/{role_id}/",
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
    name="phoxtail_palette_roles_delete",
    description=(
        "Delete a palette role. Requires `etag` from phoxtail_palette_roles_get. "
        "WARNING: this removes a CSS variable namespace from the design system — "
        "verify no templates reference this role before deleting."
    ),
)
def palette_roles_delete(role_id: int, etag: str) -> str:
    resp = request(
        "DELETE",
        f"/palette-roles/{role_id}/",
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": role_id})
