"""``/api/agent/v1/artifacts`` — ModelArtifact endpoints.

Endpoints:
- ``GET    /``          — list, optional ``?provider_uuid=``/``?search=``/``?is_active=``
- ``POST   /``          — create, returns 201 with ETag header
- ``GET    /{uuid}/``   — detail, sets ETag header
- ``PATCH  /{uuid}/``   — partial update, requires ``If-Match``
- ``DELETE /{uuid}/``   — delete (sites/conversations referencing it fall back to null)

``permission`` gates who sees the model in the picker, expressed as
``app_label.codename``; null means everyone with chatbot access.

Business-rule validation is delegated to ``Model.full_clean()``; the
shared API instance translates ``django.core.exceptions.ValidationError``
into a 422 response.
"""

from __future__ import annotations

from uuid import UUID

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError

from phoxtail.agent.api.v1._helpers import (
    artifact_detail,
    artifact_etag,
    narrow_by_search,
    require_if_match,
    resolve_artifact,
    resolve_permission,
    resolve_provider,
)
from phoxtail.agent.api.v1.schemas import (
    Artifact as ArtifactSchema,
)
from phoxtail.agent.api.v1.schemas import (
    ArtifactCreate,
    ArtifactList,
    ArtifactUpdate,
    Error,
)
from phoxtail.agent.models import ModelArtifact

router = Router()


@router.get(
    "/",
    response={200: ArtifactList, 404: Error},
    summary="List model artifacts",
)
def list_artifacts(
    request: HttpRequest,
    provider_uuid: UUID | None = Query(None, description="Restrict to one provider."),
    search: str | None = Query(None, description="Prefix search on display name and identifier."),
    is_active: bool | None = Query(None, description="Filter by active flag."),
):
    qs = ModelArtifact.objects.select_related("provider", "permission__content_type")
    if provider_uuid is not None:
        qs = qs.filter(provider=resolve_provider(provider_uuid))
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search:
        qs = narrow_by_search(qs, search)
    qs = qs.order_by("sort_order")

    artifacts = [artifact_detail(a) for a in qs]
    return {"artifacts": artifacts, "total": len(artifacts)}


@router.post(
    "/",
    response={201: ArtifactSchema, 404: Error, 422: Error},
    summary="Create a model artifact",
)
def create_artifact(
    request: HttpRequest,
    response: HttpResponse,
    payload: ArtifactCreate,
):
    data = payload.model_dump()
    permission_label = data.pop("permission")
    artifact = ModelArtifact(
        provider=resolve_provider(data.pop("provider_uuid")),
        permission=resolve_permission(permission_label) if permission_label else None,
        **data,
    )
    artifact.full_clean()
    artifact.save()
    response["ETag"] = artifact_etag(artifact)
    return 201, artifact_detail(artifact)


@router.get(
    "/{artifact_uuid}/",
    response={200: ArtifactSchema, 404: Error},
    summary="Show a model artifact by UUID",
)
def get_artifact(
    request: HttpRequest,
    response: HttpResponse,
    artifact_uuid: UUID,
):
    artifact = resolve_artifact(artifact_uuid)
    response["ETag"] = artifact_etag(artifact)
    return artifact_detail(artifact)


@router.patch(
    "/{artifact_uuid}/",
    response={200: ArtifactSchema, 404: Error, 412: Error, 422: Error, 428: Error},
    summary="Update a model artifact by UUID (optimistic concurrency)",
)
def update_artifact(
    request: HttpRequest,
    response: HttpResponse,
    artifact_uuid: UUID,
    payload: ArtifactUpdate,
):
    """Apply the fields present in the payload, guarded by ``If-Match``."""
    artifact = resolve_artifact(artifact_uuid)
    require_if_match(request, artifact_etag(artifact))

    data = payload.model_dump(exclude_unset=True)

    # ``permission`` is the one field where an explicit null is meaningful
    # (clear the gate), so it is applied on presence rather than on value.
    if "permission" in data:
        label = data.pop("permission")
        artifact.permission = resolve_permission(label) if label else None
    if "provider_uuid" in data:
        provider_uuid = data.pop("provider_uuid")
        if provider_uuid is None:
            raise HttpError(422, "provider_uuid cannot be null — every model belongs to a provider.")
        artifact.provider = resolve_provider(provider_uuid)

    for field, value in data.items():
        if value is not None:
            setattr(artifact, field, value)

    artifact.full_clean()
    artifact.save()
    response["ETag"] = artifact_etag(artifact)
    return artifact_detail(artifact)


@router.delete(
    "/{artifact_uuid}/",
    response={200: dict, 404: Error},
    summary="Delete a model artifact by UUID",
)
def delete_artifact(request: HttpRequest, artifact_uuid: UUID):
    """Delete an artifact — conversations and site defaults referencing it
    are ``SET_NULL``, so history survives."""
    artifact = resolve_artifact(artifact_uuid)
    artifact.delete()
    return {"deleted": True, "uuid": str(artifact_uuid)}
