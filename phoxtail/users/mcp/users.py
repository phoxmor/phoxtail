"""``phoxtail_users_*_user`` MCP tools.

Thin wrappers around ``/api/users/v1/users/``. Users are addressed by
UUID everywhere; writes follow the read-before-write ETag contract shared
by every Phoxtail MCP tool. The whole surface requires a superuser
token/session.
"""

from __future__ import annotations

import json
from typing import Any

from phoxtail.mcp import mcp_server
from phoxtail.users.mcp._error import error_envelope
from phoxtail.users.mcp._http import request


def _with_etag(resp) -> str:
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_users_list_users",
    description=(
        "List the project's users. Requires a superuser "
        "token/session. Optional filters: `search` (prefix search on email, "
        "username, first or last name), `is_active`. Returns summaries with "
        "each user's `uuid` — use phoxtail_users_get_user for full details."
    ),
)
def users_list_users(
    search: str | None = None,
    is_active: bool | None = None,
) -> str:
    resp = request("GET", "/users/", params={"search": search, "is_active": is_active})
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_users_get_user",
    description=(
        "Get full details of a user by UUID: profile fields (born_at, gender, "
        "country, phone_number), login metadata (date_joined, last_login) and "
        "the read-only is_superuser flag. Requires a superuser token/session. "
        "The response includes `_etag` which MUST be passed to "
        "phoxtail_users_update_user for concurrency control."
    ),
)
def users_get_user(user_uuid: str) -> str:
    resp = request("GET", f"/users/{user_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_users_create_user",
    description=(
        "Create a user without login access — no password is "
        "accepted or transported, and no email is sent. Requires a superuser "
        "token/session. Required: email, first_name, last_name. Optional: "
        "username (lowercase; omit to auto-generate from the name/email — "
        "preferred), born_at (ISO date, e.g. '1990-04-23'), gender_uuid (use "
        "phoxtail_users_list_genders to find gender UUIDs), country "
        "(ISO 3166-1 alpha-2 code, e.g. 'GR'), phone_number (E.164, e.g. "
        "'+306912345678'), is_active. Returns the created user with `_etag`. "
        "For importing many users at once use "
        "phoxtail_users_bulk_create_users instead."
    ),
)
def users_create_user(
    email: str,
    first_name: str,
    last_name: str,
    username: str | None = None,
    born_at: str | None = None,
    gender_uuid: str | None = None,
    country: str | None = None,
    phone_number: str | None = None,
    is_active: bool = True,
) -> str:
    body: dict[str, Any] = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "is_active": is_active,
    }
    for key, value in (
        ("username", username),
        ("born_at", born_at),
        ("gender_uuid", gender_uuid),
        ("country", country),
        ("phone_number", phone_number),
    ):
        if value is not None:
            body[key] = value
    resp = request("POST", "/users/", json_body=body)
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_users_update_user",
    description=(
        "Update a user. Pass only the fields you want to change — omitted "
        "fields are left untouched. Requires a superuser token/session and "
        "`etag` from a prior phoxtail_users_get_user call. Writable fields: "
        "first_name, last_name, email, username (lowercase), born_at (ISO "
        "date), gender_uuid (use phoxtail_users_list_genders to find UUIDs), "
        "country (ISO alpha-2), phone_number (E.164), is_active. "
        "is_superuser, is_staff and password are never writable. Set "
        "clear_born_at/clear_gender/clear_country/clear_phone_number=true to "
        "null out those fields. Deactivating (is_active=false) is the "
        "preferred way to remove a user — it preserves the account's "
        "related records, unlike phoxtail_users_delete_user. Returns the "
        "updated user with a fresh `_etag`."
    ),
)
def users_update_user(
    user_uuid: str,
    etag: str,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    username: str | None = None,
    born_at: str | None = None,
    gender_uuid: str | None = None,
    country: str | None = None,
    phone_number: str | None = None,
    is_active: bool | None = None,
    clear_born_at: bool = False,
    clear_gender: bool = False,
    clear_country: bool = False,
    clear_phone_number: bool = False,
) -> str:
    candidate_fields = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "username": username,
        "born_at": born_at,
        "gender_uuid": gender_uuid,
        "country": country,
        "phone_number": phone_number,
        "is_active": is_active,
    }
    fields: dict[str, Any] = {key: value for key, value in candidate_fields.items() if value is not None}
    for clear, key in (
        (clear_born_at, "born_at"),
        (clear_gender, "gender_uuid"),
        (clear_country, "country"),
        (clear_phone_number, "phone_number"),
    ):
        if clear:
            fields[key] = None

    resp = request(
        "PATCH",
        f"/users/{user_uuid}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_users_verify_email",
    description=(
        "Mark a user's email address as verified in allauth, by user UUID. "
        "Administrative bypass of the confirmation-email flow — no email is "
        "sent. Idempotent: returns status 'verified' or 'already_verified'. "
        "Requires a superuser token/session. For many users at once use "
        "phoxtail_users_bulk_verify_emails."
    ),
)
def users_verify_email(user_uuid: str) -> str:
    resp = request("POST", f"/users/{user_uuid}/verify-email/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_users_bulk_verify_emails",
    description=(
        "Mark many users' email addresses as verified in allauth. Pass "
        "`user_uuids` as a JSON array of user UUIDs (from "
        "phoxtail_users_list_users or a bulk-create response). The server "
        "caps one request at 100 rows; send chunks of ~50 for large sets. "
        "Rows are independent — an unknown UUID is reported in `results` "
        "with status 'error' and never aborts the batch. No email is sent. "
        "Requires a superuser token/session. Returns per-row results plus "
        "`verified`/`already_verified`/`failed` counts."
    ),
)
def users_bulk_verify_emails(user_uuids: list[str]) -> str:
    resp = request("POST", "/users/verify-emails/", json_body={"user_uuids": user_uuids})
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_users_delete_user",
    description=(
        "PERMANENTLY delete a user by UUID. IRREVERSIBLE and destructive: "
        "records referencing the user in installed apps cascade away with "
        "the account, along with its email records. NEVER call this unless "
        "the user explicitly asked to delete this specific account in this "
        "conversation — confirm the exact account (email + uuid) with them "
        "first. To remove a user from active use, prefer "
        "phoxtail_users_update_user with is_active=false, which preserves "
        "history. Requires a superuser token/session; the account you are "
        "authenticated as cannot be deleted."
    ),
)
def users_delete_user(user_uuid: str) -> str:
    resp = request("DELETE", f"/users/{user_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps({"deleted": True, "uuid": user_uuid})


@mcp_server.tool(
    name="phoxtail_users_bulk_create_users",
    description=(
        "Bulk create users — built for CSV imports. Requires a "
        "superuser token/session. Pass `users` as a JSON array of objects, "
        "each with required email, first_name, last_name and optional "
        "born_at (ISO date), gender_uuid, country (ISO alpha-2), "
        "phone_number (E.164), is_active. The server caps one request at "
        "100 rows; send chunks of ~50 rows for large imports. Rows are "
        "processed independently — a bad row (e.g. duplicate email) is "
        "reported in `results` with status 'error' and never aborts the "
        "batch. Exception: a malformed field type (e.g. an unparseable "
        "born_at) rejects the whole request with a 422 naming the row — fix "
        "that row and resend the batch. No passwords are set and no email "
        "is sent. Returns per-row results plus `created`/`failed` counts."
    ),
)
def users_bulk_create_users(users: list[dict[str, Any]]) -> str:
    resp = request("POST", "/users/bulk/", json_body={"users": users})
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)
