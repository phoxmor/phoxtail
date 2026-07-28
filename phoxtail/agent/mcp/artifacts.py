"""``phoxtail_agent_*_artifact`` MCP tools.

Thin wrappers around ``/api/agent/v1/artifacts/``. Artifacts are addressed
by UUID everywhere; updates follow the read-before-write ETag contract
shared by every Phoxtail MCP tool.
"""

from __future__ import annotations

import json
from typing import Any

from phoxtail.agent.mcp._error import error_envelope
from phoxtail.agent.mcp._http import request
from phoxtail.mcp import mcp_server


def _with_etag(resp) -> str:
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_agent_list_artifacts",
    description=(
        "List the models users can pick in the chatbot, ordered by "
        "`sort_order`. Optional filters: `provider_uuid` (restrict "
        "to one provider — get UUIDs from phoxtail_agent_list_providers), "
        "`search` (prefix search on display name and identifier), "
        "`is_active`. Before updating a model, fetch it with "
        "phoxtail_agent_get_artifact to obtain its `_etag`."
    ),
)
def agent_list_artifacts(
    provider_uuid: str | None = None,
    search: str | None = None,
    is_active: bool | None = None,
) -> str:
    resp = request(
        "GET",
        "/artifacts/",
        params={"provider_uuid": provider_uuid, "search": search, "is_active": is_active},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_agent_get_artifact",
    description=(
        "Get a model artifact by UUID, including its provider and the "
        "permission gating it. The response includes `_etag` which MUST be "
        "passed to phoxtail_agent_update_artifact for concurrency control."
    ),
)
def agent_get_artifact(artifact_uuid: str) -> str:
    resp = request("GET", f"/artifacts/{artifact_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_agent_create_artifact",
    description=(
        "Add a model to a provider, making it selectable in the chatbot's "
        "model picker. Required: provider_uuid (from "
        "phoxtail_agent_list_providers), identifier (the model id exactly as "
        "the provider's API expects it, e.g. 'gemini-3-flash-preview'), "
        "display_name (what users see, e.g. 'Gemini 3 Flash'). Optional: "
        "sort_order (lower sorts first in the picker), permission "
        "('app_label.codename' — only users holding it see the model; omit "
        "for everyone with chatbot access), is_active. The identifier must "
        "be unique within its provider. Returns the created model with its "
        "`uuid` and `_etag`."
    ),
)
def agent_create_artifact(
    provider_uuid: str,
    identifier: str,
    display_name: str,
    sort_order: int = 0,
    permission: str | None = None,
    is_active: bool = True,
) -> str:
    body: dict[str, Any] = {
        "provider_uuid": provider_uuid,
        "identifier": identifier,
        "display_name": display_name,
        "sort_order": sort_order,
        "is_active": is_active,
    }
    if permission is not None:
        body["permission"] = permission
    resp = request("POST", "/artifacts/", json_body=body)
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_agent_update_artifact",
    description=(
        "Update a model artifact. Pass only the fields you want to change — "
        "omitted fields are left untouched. Requires `etag` from a prior "
        "phoxtail_agent_get_artifact call. Writable: identifier, "
        "display_name, provider_uuid (move the model to another provider), "
        "sort_order, permission ('app_label.codename'), is_active. Set "
        "clear_permission=true to make the model visible to everyone with "
        "chatbot access. Setting is_active=false removes it from the picker "
        "while keeping past conversations intact — prefer this over "
        "phoxtail_agent_delete_artifact for retiring a model. Returns the "
        "updated model with a fresh `_etag`."
    ),
)
def agent_update_artifact(
    artifact_uuid: str,
    etag: str,
    identifier: str | None = None,
    display_name: str | None = None,
    provider_uuid: str | None = None,
    sort_order: int | None = None,
    permission: str | None = None,
    is_active: bool | None = None,
    clear_permission: bool = False,
) -> str:
    candidate_fields = {
        "identifier": identifier,
        "display_name": display_name,
        "provider_uuid": provider_uuid,
        "sort_order": sort_order,
        "permission": permission,
        "is_active": is_active,
    }
    fields: dict[str, Any] = {key: value for key, value in candidate_fields.items() if value is not None}
    if clear_permission:
        fields["permission"] = None

    resp = request(
        "PATCH",
        f"/artifacts/{artifact_uuid}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_agent_delete_artifact",
    description=(
        "Delete a model artifact by UUID. Past conversations that used it "
        "survive and simply lose their model reference; a site that "
        "defaulted to it is left without a default, so users must pick a "
        "model per conversation. To retire a model reversibly, prefer "
        "phoxtail_agent_update_artifact with is_active=false."
    ),
)
def agent_delete_artifact(artifact_uuid: str) -> str:
    resp = request("DELETE", f"/artifacts/{artifact_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)
