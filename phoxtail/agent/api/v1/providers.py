"""``/api/agent/v1/providers`` — InferenceProvider endpoints.

Endpoints:
- ``GET    /``          — list, optional ``?search=``/``?is_active=`` filters
- ``POST   /``          — create, returns 201 with ETag header
- ``GET    /{uuid}/``   — detail, sets ETag header
- ``PATCH  /{uuid}/``   — partial update, requires ``If-Match``
- ``DELETE /{uuid}/``   — delete, cascading to the provider's artifacts

``api_key_env_var`` names the environment variable holding the key — the
key itself never travels through this API and is set in ``.env`` by hand.

Business-rule validation is delegated to ``Model.full_clean()``; the
shared API instance translates ``django.core.exceptions.ValidationError``
into a 422 response.
"""

from __future__ import annotations

from uuid import UUID

from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router

from phoxtail.agent.api.v1._helpers import (
    narrow_by_search,
    provider_detail,
    provider_etag,
    require_if_match,
    resolve_provider,
)
from phoxtail.agent.api.v1.schemas import (
    Error,
    ProviderCreate,
    ProviderList,
    ProviderUpdate,
)
from phoxtail.agent.api.v1.schemas import (
    Provider as ProviderSchema,
)
from phoxtail.agent.models import InferenceProvider

router = Router()


@router.get(
    "/",
    response={200: ProviderList},
    summary="List inference providers",
)
def list_providers(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on display name."),
    is_active: bool | None = Query(None, description="Filter by active flag."),
):
    qs = InferenceProvider.objects.annotate(artifact_count=Count("artifacts"))
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search:
        qs = narrow_by_search(qs, search)

    providers = [provider_detail(p) for p in qs]
    return {"providers": providers, "total": len(providers)}


@router.post(
    "/",
    response={201: ProviderSchema, 422: Error},
    summary="Create an inference provider",
)
def create_provider(
    request: HttpRequest,
    response: HttpResponse,
    payload: ProviderCreate,
):
    provider = InferenceProvider(**payload.model_dump())
    provider.full_clean()
    provider.save()
    response["ETag"] = provider_etag(provider)
    return 201, provider_detail(provider)


@router.get(
    "/{provider_uuid}/",
    response={200: ProviderSchema, 404: Error},
    summary="Show an inference provider by UUID",
)
def get_provider(
    request: HttpRequest,
    response: HttpResponse,
    provider_uuid: UUID,
):
    provider = resolve_provider(provider_uuid)
    response["ETag"] = provider_etag(provider)
    return provider_detail(provider)


@router.patch(
    "/{provider_uuid}/",
    response={200: ProviderSchema, 404: Error, 412: Error, 422: Error, 428: Error},
    summary="Update an inference provider by UUID (optimistic concurrency)",
)
def update_provider(
    request: HttpRequest,
    response: HttpResponse,
    provider_uuid: UUID,
    payload: ProviderUpdate,
):
    """Apply the fields present in the payload, guarded by ``If-Match``."""
    provider = resolve_provider(provider_uuid)
    require_if_match(request, provider_etag(provider))

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(provider, field, value)

    provider.full_clean()
    provider.save()
    response["ETag"] = provider_etag(provider)
    return provider_detail(provider)


@router.delete(
    "/{provider_uuid}/",
    response={200: dict, 404: Error},
    summary="Delete an inference provider and all of its model artifacts",
)
def delete_provider(request: HttpRequest, provider_uuid: UUID):
    """Delete a provider — its artifacts cascade away with it.

    The deleted artifact count is returned so callers can report the
    blast radius.
    """
    provider = resolve_provider(provider_uuid)
    artifact_count = provider.artifacts.count()
    provider.delete()
    return {"deleted": True, "uuid": str(provider_uuid), "artifacts_deleted": artifact_count}
