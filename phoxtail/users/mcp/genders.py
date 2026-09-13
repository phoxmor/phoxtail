"""``phoxtail_users_*_gender`` MCP tools.

Thin wrappers around ``/api/users/v1/genders/``. Genders are addressed by
UUID everywhere; updates follow the read-before-write ETag contract shared
by every Phoxtail MCP tool. The whole surface requires a superuser
token/session.
"""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.mcp.authorization import scoped
from phoxtail.users.mcp._error import error_envelope
from phoxtail.users.mcp._http import request


def _with_etag(resp) -> str:
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_users_list_genders",
    auth=[scoped("phoxtail_users.view_gender")],
    description=(
        "List the project's gender options with their UUIDs — use these "
        "UUIDs as `gender_uuid` in phoxtail_users_create_user, "
        "phoxtail_users_update_user and phoxtail_users_bulk_create_users. "
        "Requires a superuser token/session. Optional filter: `search` "
        "(prefix search on name). Before updating a gender, fetch it with "
        "phoxtail_users_get_gender to obtain its `_etag`."
    ),
)
def users_list_genders(search: str | None = None) -> str:
    resp = request("GET", "/genders/", params={"search": search})
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_users_get_gender",
    auth=[scoped("phoxtail_users.view_gender")],
    description=(
        "Get a gender option by UUID. Requires a superuser token/session. "
        "The response includes `_etag` which MUST be passed to "
        "phoxtail_users_update_gender for concurrency control."
    ),
)
def users_get_gender(gender_uuid: str) -> str:
    resp = request("GET", f"/genders/{gender_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_users_create_gender",
    auth=[scoped("phoxtail_users.add_gender")],
    description=(
        "Create a gender option. Requires a superuser token/session. "
        "Required: name (unique, e.g. 'Female'). Optional: symbol (short "
        "unique marker, e.g. '♀' or 'F'). Returns the created gender with "
        "its `uuid` and `_etag`."
    ),
)
def users_create_gender(name: str, symbol: str | None = None) -> str:
    body: dict = {"name": name}
    if symbol is not None:
        body["symbol"] = symbol
    resp = request("POST", "/genders/", json_body=body)
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_users_update_gender",
    auth=[scoped("phoxtail_users.change_gender")],
    description=(
        "Update a gender option. Pass only the fields you want to change. "
        "Requires a superuser token/session and `etag` from a prior "
        "phoxtail_users_get_gender (or create) response. Writable: name, "
        "symbol. "
        "Set clear_symbol=true to remove the symbol. Returns the updated "
        "gender with a fresh `_etag`."
    ),
)
def users_update_gender(
    gender_uuid: str,
    etag: str,
    name: str | None = None,
    symbol: str | None = None,
    clear_symbol: bool = False,
) -> str:
    fields: dict = {}
    if name is not None:
        fields["name"] = name
    if symbol is not None:
        fields["symbol"] = symbol
    if clear_symbol:
        fields["symbol"] = None

    resp = request(
        "PATCH",
        f"/genders/{gender_uuid}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_users_delete_gender",
    auth=[scoped("phoxtail_users.delete_gender")],
    description=(
        "Delete a gender option by UUID. Requires a superuser token/session. "
        "Safe for accounts: users referencing the gender keep their account "
        "and their gender becomes unset (null)."
    ),
)
def users_delete_gender(gender_uuid: str) -> str:
    resp = request("DELETE", f"/genders/{gender_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": True, "uuid": gender_uuid})
