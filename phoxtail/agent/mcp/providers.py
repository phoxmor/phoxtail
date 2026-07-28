"""``phoxtail_agent_*_provider`` MCP tools.

Thin wrappers around ``/api/agent/v1/providers/``. Providers are addressed
by UUID everywhere; updates follow the read-before-write ETag contract
shared by every Phoxtail MCP tool.
"""

from __future__ import annotations

import json

from phoxtail.agent.mcp._error import error_envelope
from phoxtail.agent.mcp._http import request
from phoxtail.mcp import mcp_server


def _with_etag(resp) -> str:
    data = resp.json()
    data["_etag"] = resp.headers.get("ETag", "")
    return json.dumps(data, indent=2)


@mcp_server.tool(
    name="phoxtail_agent_list_providers",
    description=(
        "List the inference providers the project's chatbot can use, with "
        "their UUIDs — use these as `provider_uuid` in "
        "phoxtail_agent_create_artifact. Optional filters: `search` (prefix "
        "search on display name), `is_active`. Each entry includes "
        "`artifact_count`. Before updating a provider, fetch it with "
        "phoxtail_agent_get_provider to obtain its `_etag`."
    ),
)
def agent_list_providers(search: str | None = None, is_active: bool | None = None) -> str:
    resp = request("GET", "/providers/", params={"search": search, "is_active": is_active})
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)


@mcp_server.tool(
    name="phoxtail_agent_get_provider",
    description=(
        "Get an inference provider by UUID. The response includes `_etag` "
        "which MUST be passed to phoxtail_agent_update_provider for "
        "concurrency control."
    ),
)
def agent_get_provider(provider_uuid: str) -> str:
    resp = request("GET", f"/providers/{provider_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_agent_create_provider",
    description=(
        "Create an inference provider — a model family the chatbot can talk "
        "to. Required: identifier (unique slug, e.g. 'google-gemini'), "
        "display_name. Then configure ONE of two connection styles:\n"
        "1. A provider pydantic-ai supports natively: set `model_prefix` to "
        "its pydantic-ai prefix (e.g. 'google-gla', 'anthropic', 'openai') "
        "and leave base_url empty. Models are then addressed as "
        "'<model_prefix>:<artifact identifier>'.\n"
        "2. Any OpenAI-compatible endpoint: set `base_url` (e.g. "
        "'https://api.example.com/v1') and leave model_prefix empty.\n"
        "`api_key_env_var` names the environment variable holding the API "
        "key (e.g. 'GEMINI_API_KEY'). This tool does NOT set the key — a "
        "human must add it to the project's .env and restart, or chat turns "
        "on this provider will fail. Add models with "
        "phoxtail_agent_create_artifact. Returns the created provider with "
        "its `uuid` and `_etag`."
    ),
)
def agent_create_provider(
    identifier: str,
    display_name: str,
    model_prefix: str = "",
    base_url: str = "",
    api_key_env_var: str = "",
    is_active: bool = True,
) -> str:
    body = {
        "identifier": identifier,
        "display_name": display_name,
        "model_prefix": model_prefix,
        "base_url": base_url,
        "api_key_env_var": api_key_env_var,
        "is_active": is_active,
    }
    resp = request("POST", "/providers/", json_body=body)
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_agent_update_provider",
    description=(
        "Update an inference provider. Pass only the fields you want to "
        "change — omitted fields are left untouched. Requires `etag` from a "
        "prior phoxtail_agent_get_provider call. Writable: identifier, "
        "display_name, model_prefix, base_url, api_key_env_var, is_active. "
        "Setting is_active=false hides every model under this provider from "
        "the picker without deleting anything. Returns the updated provider "
        "with a fresh `_etag`."
    ),
)
def agent_update_provider(
    provider_uuid: str,
    etag: str,
    identifier: str | None = None,
    display_name: str | None = None,
    model_prefix: str | None = None,
    base_url: str | None = None,
    api_key_env_var: str | None = None,
    is_active: bool | None = None,
) -> str:
    candidate_fields = {
        "identifier": identifier,
        "display_name": display_name,
        "model_prefix": model_prefix,
        "base_url": base_url,
        "api_key_env_var": api_key_env_var,
        "is_active": is_active,
    }
    fields = {key: value for key, value in candidate_fields.items() if value is not None}

    resp = request(
        "PATCH",
        f"/providers/{provider_uuid}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_agent_delete_provider",
    description=(
        "DESTRUCTIVE: delete an inference provider by UUID and every model "
        "artifact under it. Sites that defaulted to one of those models are "
        "left without a default, and past conversations lose their model "
        "reference (the conversations themselves survive). To take a "
        "provider out of use reversibly, prefer "
        "phoxtail_agent_update_provider with is_active=false. Only call this "
        "when the user explicitly asked to delete this provider. Returns "
        "`artifacts_deleted`."
    ),
)
def agent_delete_provider(provider_uuid: str) -> str:
    resp = request("DELETE", f"/providers/{provider_uuid}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return json.dumps(resp.json(), indent=2)
