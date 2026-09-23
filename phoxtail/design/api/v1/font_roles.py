"""``/api/design/v1/font-roles/`` — FontRole CRUD."""

from __future__ import annotations

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Schema
from ninja.errors import HttpError

from phoxtail.api.auth import guarded
from phoxtail.api.pagination import Router
from phoxtail.api.search import narrow_by_search
from phoxtail.design.api.v1._helpers import (
    font_role_etag,
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


@router.get(
    "/",
    response={200: list[FontRoleSummary]},
    summary="List font roles",
    auth=guarded("phoxtail_design.view_fontrole"),
)
def list_font_roles(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on name and identifier."),
):
    from phoxtail.design.models import FontRole

    qs = FontRole.objects.order_by("name")
    if search:
        qs = narrow_by_search(qs, search)
    return qs


@router.post(
    "/",
    response={201: FontRoleSummary, 400: Error, 409: Error},
    summary="Create a font role",
    auth=guarded("phoxtail_design.add_fontrole"),
)
def create_font_role(request: HttpRequest, response: HttpResponse, payload: FontRoleCreate):
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
            f"A font role with name '{payload.name}' or identifier '{payload.identifier}' already exists.",
        )
    response["ETag"] = font_role_etag(r)
    return 201, r


@router.get(
    "/{role_id}/",
    response={200: FontRoleSummary, 404: Error},
    summary="Get a font role",
    auth=guarded("phoxtail_design.view_fontrole"),
)
def get_font_role(request: HttpRequest, response: HttpResponse, role_id: int):
    r = resolve_font_role(role_id)
    response["ETag"] = font_role_etag(r)
    return r


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
    auth=guarded("phoxtail_design.change_fontrole"),
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
    return r


@router.delete(
    "/{role_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a font role",
    auth=guarded("phoxtail_design.delete_fontrole"),
)
def delete_font_role(request: HttpRequest, role_id: int):
    r = resolve_font_role(role_id)
    require_if_match(request, font_role_etag(r))
    r.delete()
    return 204, None
