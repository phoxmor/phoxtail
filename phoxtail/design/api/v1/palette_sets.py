"""``/api/design/v1/palette-sets/`` — PaletteSet CRUD."""

from __future__ import annotations

from datetime import datetime

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Schema
from ninja.errors import HttpError

from phoxtail.api.auth import guarded
from phoxtail.api.pagination import Router
from phoxtail.api.search import narrow_by_search
from phoxtail.design.api.v1._helpers import (
    palette_set_etag,
    require_if_match,
    resolve_palette_set,
)

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PaletteSetSummary(Schema):
    id: int
    name: str
    identifier: str
    description: str
    palette_count: int
    created_at: datetime | None = None
    updated_at: datetime

    @staticmethod
    def resolve_palette_count(palette_set) -> int:
        # Annotated onto the list's query; one row counts itself.
        if "palette_count" in palette_set.__dict__:
            return palette_set.palette_count
        return palette_set.palettes.count()


class PaletteSetCreate(Schema):
    name: str
    identifier: str
    description: str = ""


class PaletteSetPatch(Schema):
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
    response={200: list[PaletteSetSummary]},
    summary="List palette sets",
    auth=guarded("phoxtail_design.view_paletteset"),
)
def list_palette_sets(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on name and identifier."),
):
    from django.db.models import Count

    from phoxtail.design.models import PaletteSet

    qs = PaletteSet.objects.annotate(palette_count=Count("palettes")).order_by("name")
    if search:
        qs = narrow_by_search(qs, search)
    return qs


@router.post(
    "/",
    response={201: PaletteSetSummary, 400: Error, 409: Error},
    summary="Create a palette set",
    auth=guarded("phoxtail_design.add_paletteset"),
)
def create_palette_set(request: HttpRequest, response: HttpResponse, payload: PaletteSetCreate):
    from phoxtail.design.models import PaletteSet

    try:
        ps = PaletteSet.objects.create(
            name=payload.name,
            identifier=payload.identifier,
            description=payload.description,
        )
    except IntegrityError:
        raise HttpError(
            409,
            f"A palette set with name '{payload.name}' or identifier '{payload.identifier}' already exists.",
        )
    response["ETag"] = palette_set_etag(ps)
    return 201, ps


@router.get(
    "/{palette_set_id}/",
    response={200: PaletteSetSummary, 404: Error},
    summary="Get a palette set",
    auth=guarded("phoxtail_design.view_paletteset"),
)
def get_palette_set(request: HttpRequest, response: HttpResponse, palette_set_id: int):
    from django.db.models import Count

    from phoxtail.design.models import PaletteSet

    try:
        ps = PaletteSet.objects.annotate(_palette_count=Count("palettes")).get(pk=palette_set_id)
    except PaletteSet.DoesNotExist:
        raise HttpError(404, f"PaletteSet {palette_set_id} not found.")
    response["ETag"] = palette_set_etag(ps)
    return ps


@router.patch(
    "/{palette_set_id}/",
    response={
        200: PaletteSetSummary,
        400: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a palette set",
    auth=guarded("phoxtail_design.change_paletteset"),
)
def patch_palette_set(
    request: HttpRequest,
    response: HttpResponse,
    palette_set_id: int,
    payload: PaletteSetPatch,
):
    ps = resolve_palette_set(palette_set_id)
    require_if_match(request, palette_set_etag(ps))

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(ps, field, value)
    try:
        ps.save()
    except IntegrityError:
        raise HttpError(409, "A palette set with that name or identifier already exists.")

    response["ETag"] = palette_set_etag(ps)
    return ps


@router.delete(
    "/{palette_set_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a palette set",
    auth=guarded("phoxtail_design.delete_paletteset"),
)
def delete_palette_set(request: HttpRequest, palette_set_id: int):
    ps = resolve_palette_set(palette_set_id)
    require_if_match(request, palette_set_etag(ps))
    ps.delete()
    return 204, None
