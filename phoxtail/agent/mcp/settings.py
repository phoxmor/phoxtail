"""``phoxtail_agent_settings_*`` MCP tools.

Thin wrappers around ``/api/agent/v1/settings/{site_id}/`` — the per-site
default model. Read/update only: the record is a singleton per Wagtail
site and is auto-created on first read.
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
    name="phoxtail_agent_get_settings",
    description=(
        "Get a site's agent settings — the model new chat conversations "
        "start with. Auto-creates a blank record if none exists yet. Use "
        "phoxtail_sites_list to find site IDs. The response includes "
        "`_etag` which MUST be passed to phoxtail_agent_update_settings for "
        "concurrency control."
    ),
)
def agent_get_settings(site_id: int) -> str:
    resp = request("GET", f"/settings/{site_id}/")
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)


@mcp_server.tool(
    name="phoxtail_agent_update_settings",
    description=(
        "Set a site's default chatbot model. Pass `default_artifact_uuid` "
        "(from phoxtail_agent_list_artifacts), or clear_default=true to "
        "unset it — with no default, users must pick a model for every "
        "conversation. Requires `etag` from a prior "
        "phoxtail_agent_get_settings call. Returns the updated settings "
        "with a fresh `_etag`."
    ),
)
def agent_update_settings(
    site_id: int,
    etag: str,
    default_artifact_uuid: str | None = None,
    clear_default: bool = False,
) -> str:
    fields: dict = {}
    if default_artifact_uuid is not None:
        fields["default_artifact_uuid"] = default_artifact_uuid
    if clear_default:
        fields["default_artifact_uuid"] = None

    resp = request(
        "PATCH",
        f"/settings/{site_id}/",
        json_body=fields,
        headers={"If-Match": etag},
    )
    env = error_envelope(resp)
    if env is not None:
        return env
    return _with_etag(resp)
