"""``/api/design/v1/palette-sets/`` — PaletteSet CRUD."""

from __future__ import annotations

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.design.v1._helpers import (
    palette_set_etag,
    palette_set_summary,
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
    created_at: str | None
    updated_at: str


class PaletteSetList(Schema):
    palette_sets: list[PaletteSetSummary]
    total: int


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


@router.get("/", response={200: PaletteSetList}, summary="List palette sets")
def list_palette_sets(
    request: HttpRequest,
    search: str | None = Query(
        None, description="Prefix search on name and identifier."
    ),
):
    from django.db.models import Count

    from phoxtail.design.models import PaletteSet

    qs = PaletteSet.objects.annotate(_palette_count=Count("palettes")).order_by("name")
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    items = [palette_set_summary(ps) for ps in qs]
    return {"palette_sets": items, "total": len(items)}


@router.post(
    "/",
    response={201: PaletteSetSummary, 400: Error, 409: Error},
    summary="Create a palette set",
)
def create_palette_set(
    request: HttpRequest, response: HttpResponse, payload: PaletteSetCreate
):
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
            f"A palette set with name '{payload.name}' or identifier "
            f"'{payload.identifier}' already exists.",
        )
    response["ETag"] = palette_set_etag(ps)
    return 201, palette_set_summary(ps)


@router.get(
    "/{palette_set_id}/",
    response={200: PaletteSetSummary, 404: Error},
    summary="Get a palette set",
)
def get_palette_set(request: HttpRequest, response: HttpResponse, palette_set_id: int):
    from django.db.models import Count

    from phoxtail.design.models import PaletteSet

    try:
        ps = PaletteSet.objects.annotate(_palette_count=Count("palettes")).get(
            pk=palette_set_id
        )
    except PaletteSet.DoesNotExist:
        raise HttpError(404, f"PaletteSet {palette_set_id} not found.")
    response["ETag"] = palette_set_etag(ps)
    return palette_set_summary(ps)


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
        raise HttpError(
            409, "A palette set with that name or identifier already exists."
        )

    response["ETag"] = palette_set_etag(ps)
    return palette_set_summary(ps)


@router.delete(
    "/{palette_set_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a palette set",
)
def delete_palette_set(request: HttpRequest, palette_set_id: int):
    ps = resolve_palette_set(palette_set_id)
    require_if_match(request, palette_set_etag(ps))
    ps.delete()
    return 204, None
