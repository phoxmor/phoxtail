"""``/api/agent/v1/settings/{site_id}/`` — AgentSiteSetting read/update.

AgentSiteSetting is a singleton per Wagtail Site. There is no create or
delete — GET auto-creates a blank record if none exists yet, mirroring
``/api/cms/v1/site-settings/``.

Endpoints:
- ``GET   /{site_id}/``  — get (or auto-create) agent settings, sets ETag
- ``PATCH /{site_id}/``  — set or clear the site's default model (If-Match)
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Router

from phoxtail.agent.api.v1._helpers import (
    agent_setting_detail,
    agent_setting_etag,
    require_if_match,
    resolve_agent_setting,
    resolve_artifact,
)
from phoxtail.agent.api.v1.schemas import AgentSettings, AgentSettingsUpdate, Error

router = Router()


@router.get(
    "/{site_id}/",
    response={200: AgentSettings, 404: Error},
    summary="Show a site's agent settings",
)
def get_agent_settings(request: HttpRequest, response: HttpResponse, site_id: int):
    setting = resolve_agent_setting(site_id)
    response["ETag"] = agent_setting_etag(setting)
    return agent_setting_detail(setting)


@router.patch(
    "/{site_id}/",
    response={200: AgentSettings, 404: Error, 412: Error, 428: Error},
    summary="Set or clear a site's default model (optimistic concurrency)",
)
def update_agent_settings(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    payload: AgentSettingsUpdate,
):
    setting = resolve_agent_setting(site_id)
    require_if_match(request, agent_setting_etag(setting))

    data = payload.model_dump(exclude_unset=True)
    # An explicit null clears the default, so presence — not truthiness —
    # decides whether the field is applied.
    if "default_artifact_uuid" in data:
        artifact_uuid = data["default_artifact_uuid"]
        setting.default_artifact = resolve_artifact(artifact_uuid) if artifact_uuid else None
    setting.save()

    response["ETag"] = agent_setting_etag(setting)
    return agent_setting_detail(setting)
