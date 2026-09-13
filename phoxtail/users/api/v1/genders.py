"""``/api/users/v1/genders`` — Gender endpoints (superuser-only surface).

Endpoints:
- ``GET    /``          — list, optional ``?search=`` filter
- ``POST   /``          — create, returns 201 with ETag header
- ``GET    /{uuid}/``   — detail, sets ETag header
- ``PATCH  /{uuid}/``   — partial update, requires ``If-Match``
- ``DELETE /{uuid}/``   — delete (users referencing it fall back to null)

Business-rule validation is delegated to ``Model.full_clean()``; the
shared API instance translates ``django.core.exceptions.ValidationError``
into a 422 response.
"""

from __future__ import annotations

from uuid import UUID

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from wagtail.search.backends import get_search_backend

from phoxtail.api.auth import guarded
from phoxtail.users.api.v1._helpers import (
    delete_guarded,
    gender_detail,
    gender_etag,
    require_if_match,
    resolve_gender,
)
from phoxtail.users.api.v1.schemas import (
    Error,
    GenderCreate,
    GenderList,
    GenderUpdate,
)
from phoxtail.users.api.v1.schemas import (
    Gender as GenderSchema,
)
from phoxtail.users.models import Gender

router = Router()


@router.get(
    "/",
    response={200: GenderList, 403: Error},
    summary="List Genders",
    auth=guarded("phoxtail_users.view_gender"),
)
def list_genders(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on gender name."),
):
    qs = Gender.objects.all()
    if search:
        qs = get_search_backend().autocomplete(search, qs)

    genders = [gender_detail(g) for g in qs]
    return {"genders": genders, "total": len(genders)}


@router.post(
    "/",
    response={201: GenderSchema, 403: Error, 422: Error},
    summary="Create a Gender",
    auth=guarded("phoxtail_users.add_gender"),
)
def create_gender(
    request: HttpRequest,
    response: HttpResponse,
    payload: GenderCreate,
):
    # ``symbol`` is unique-but-nullable: store empty strings as NULL so
    # multiple symbol-less genders don't collide on uniqueness.
    gender = Gender(name=payload.name, symbol=payload.symbol or None)
    gender.full_clean()
    gender.save()
    response["ETag"] = gender_etag(gender)
    return 201, gender_detail(gender)


@router.get(
    "/{gender_uuid}/",
    response={200: GenderSchema, 403: Error, 404: Error},
    summary="Show a Gender by UUID",
    auth=guarded("phoxtail_users.view_gender"),
)
def get_gender(
    request: HttpRequest,
    response: HttpResponse,
    gender_uuid: UUID,
):
    gender = resolve_gender(gender_uuid)
    response["ETag"] = gender_etag(gender)
    return gender_detail(gender)


@router.patch(
    "/{gender_uuid}/",
    response={200: GenderSchema, 403: Error, 404: Error, 412: Error, 422: Error, 428: Error},
    summary="Update a Gender by UUID (optimistic concurrency)",
    auth=guarded("phoxtail_users.change_gender"),
)
def update_gender(
    request: HttpRequest,
    response: HttpResponse,
    gender_uuid: UUID,
    payload: GenderUpdate,
):
    """Apply the fields present in the payload, guarded by ``If-Match``."""
    gender = resolve_gender(gender_uuid)
    require_if_match(request, gender_etag(gender))

    if "name" in payload.model_fields_set and payload.name is not None:
        gender.name = payload.name
    if "symbol" in payload.model_fields_set:
        gender.symbol = payload.symbol or None

    gender.full_clean()
    gender.save()
    response["ETag"] = gender_etag(gender)
    return gender_detail(gender)


@router.delete(
    "/{gender_uuid}/",
    response={204: None, 403: Error, 404: Error, 409: Error},
    summary="Delete a Gender by UUID (users referencing it are set to null)",
    auth=guarded("phoxtail_users.delete_gender"),
)
def delete_gender(request: HttpRequest, gender_uuid: UUID):
    gender = resolve_gender(gender_uuid)
    delete_guarded(gender)
    return 204, None
