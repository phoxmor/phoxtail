"""``/api/design/v1/palette-roles/`` — PaletteRole CRUD."""

from __future__ import annotations

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.design.v1._helpers import (
    palette_role_etag,
    palette_role_summary,
    require_if_match,
    resolve_palette_role,
)

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PaletteRoleSummary(Schema):
    id: int
    name: str
    identifier: str
    description: str


class PaletteRoleList(Schema):
    palette_roles: list[PaletteRoleSummary]
    total: int


class PaletteRoleCreate(Schema):
    name: str
    identifier: str
    description: str = ""


class PaletteRolePatch(Schema):
    name: str | None = None
    identifier: str | None = None
    description: str | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response={200: PaletteRoleList}, summary="List palette roles")
def list_palette_roles(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on name and identifier."),
):
    from phoxtail.design.models import PaletteRole

    qs = PaletteRole.objects.order_by("name")
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    items = [palette_role_summary(r) for r in qs]
    return {"palette_roles": items, "total": len(items)}


@router.post(
    "/",
    response={201: PaletteRoleSummary, 400: Error, 409: Error},
    summary="Create a palette role",
)
def create_palette_role(request: HttpRequest, response: HttpResponse, payload: PaletteRoleCreate):
    from phoxtail.design.models import PaletteRole

    try:
        r = PaletteRole.objects.create(
            name=payload.name,
            identifier=payload.identifier,
            description=payload.description,
        )
    except IntegrityError:
        raise HttpError(
            409,
            f"A palette role with name '{payload.name}' or identifier '{payload.identifier}' already exists.",
        )
    response["ETag"] = palette_role_etag(r)
    return 201, palette_role_summary(r)


@router.get(
    "/{role_id}/",
    response={200: PaletteRoleSummary, 404: Error},
    summary="Get a palette role",
)
def get_palette_role(request: HttpRequest, response: HttpResponse, role_id: int):
    r = resolve_palette_role(role_id)
    response["ETag"] = palette_role_etag(r)
    return palette_role_summary(r)


@router.patch(
    "/{role_id}/",
    response={
        200: PaletteRoleSummary,
        400: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a palette role",
)
def patch_palette_role(
    request: HttpRequest,
    response: HttpResponse,
    role_id: int,
    payload: PaletteRolePatch,
):
    r = resolve_palette_role(role_id)
    require_if_match(request, palette_role_etag(r))

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(r, field, value)
    try:
        r.save()
    except IntegrityError:
        raise HttpError(409, "A palette role with that name or identifier already exists.")

    response["ETag"] = palette_role_etag(r)
    return palette_role_summary(r)


@router.delete(
    "/{role_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a palette role",
)
def delete_palette_role(request: HttpRequest, role_id: int):
    r = resolve_palette_role(role_id)
    require_if_match(request, palette_role_etag(r))
    r.delete()
    return 204, None
