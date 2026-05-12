"""``/api/design/v1/font-roles/`` — FontRole CRUD."""

from __future__ import annotations

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.design.v1._helpers import (
    font_role_etag,
    font_role_summary,
    require_if_match,
    resolve_font_role,
)

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FontRoleSummary(Schema):
    id: int
    name: str
    identifier: str
    description: str


class FontRoleList(Schema):
    font_roles: list[FontRoleSummary]
    total: int


class FontRoleCreate(Schema):
    name: str
    identifier: str
    description: str = ""


class FontRolePatch(Schema):
    name: str | None = None
    identifier: str | None = None
    description: str | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response={200: FontRoleList}, summary="List font roles")
def list_font_roles(
    request: HttpRequest,
    search: str | None = Query(
        None, description="Prefix search on name and identifier."
    ),
):
    from phoxtail.design.models import FontRole

    qs = FontRole.objects.order_by("name")
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    items = [font_role_summary(r) for r in qs]
    return {"font_roles": items, "total": len(items)}


@router.post(
    "/",
    response={201: FontRoleSummary, 400: Error, 409: Error},
    summary="Create a font role",
)
def create_font_role(
    request: HttpRequest, response: HttpResponse, payload: FontRoleCreate
):
    from phoxtail.design.models import FontRole

    try:
        r = FontRole.objects.create(
            name=payload.name,
            identifier=payload.identifier,
            description=payload.description,
        )
    except IntegrityError:
        raise HttpError(
            409,
            f"A font role with name '{payload.name}' or identifier "
            f"'{payload.identifier}' already exists.",
        )
    response["ETag"] = font_role_etag(r)
    return 201, font_role_summary(r)


@router.get(
    "/{role_id}/",
    response={200: FontRoleSummary, 404: Error},
    summary="Get a font role",
)
def get_font_role(request: HttpRequest, response: HttpResponse, role_id: int):
    r = resolve_font_role(role_id)
    response["ETag"] = font_role_etag(r)
    return font_role_summary(r)


@router.patch(
    "/{role_id}/",
    response={
        200: FontRoleSummary,
        400: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a font role",
)
def patch_font_role(
    request: HttpRequest,
    response: HttpResponse,
    role_id: int,
    payload: FontRolePatch,
):
    r = resolve_font_role(role_id)
    require_if_match(request, font_role_etag(r))

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(r, field, value)
    try:
        r.save()
    except IntegrityError:
        raise HttpError(409, "A font role with that name or identifier already exists.")

    response["ETag"] = font_role_etag(r)
    return font_role_summary(r)


@router.delete(
    "/{role_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a font role",
)
def delete_font_role(request: HttpRequest, role_id: int):
    r = resolve_font_role(role_id)
    require_if_match(request, font_role_etag(r))
    r.delete()
    return 204, None
