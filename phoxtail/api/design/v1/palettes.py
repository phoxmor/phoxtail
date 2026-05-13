"""``/api/design/v1/palettes/`` — Palette CRUD."""

from __future__ import annotations

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.design.v1._helpers import (
    palette_etag,
    palette_summary,
    require_if_match,
    resolve_palette,
)

router = Router()

_SHADES = (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PaletteSummary(Schema):
    id: int
    palette_set_id: int
    palette_set_name: str
    title: str
    description: str
    sort_order: int
    shades: dict
    created_at: str | None
    updated_at: str


class PaletteList(Schema):
    palettes: list[PaletteSummary]
    total: int


class PaletteCreate(Schema):
    palette_set_id: int
    title: str
    description: str = ""
    sort_order: int | None = None
    shade_50: str
    shade_100: str
    shade_200: str
    shade_300: str
    shade_400: str
    shade_500: str
    shade_600: str
    shade_700: str
    shade_800: str
    shade_900: str
    shade_950: str


class PalettePatch(Schema):
    palette_set_id: int | None = None
    title: str | None = None
    description: str | None = None
    sort_order: int | None = None
    shade_50: str | None = None
    shade_100: str | None = None
    shade_200: str | None = None
    shade_300: str | None = None
    shade_400: str | None = None
    shade_500: str | None = None
    shade_600: str | None = None
    shade_700: str | None = None
    shade_800: str | None = None
    shade_900: str | None = None
    shade_950: str | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response={200: PaletteList}, summary="List palettes")
def list_palettes(
    request: HttpRequest,
    palette_set_id: int | None = Query(None, description="Filter by palette set."),
    search: str | None = Query(None, description="Prefix search on palette title."),
):
    from phoxtail.design.models import Palette

    qs = Palette.objects.select_related("palette_set").order_by("palette_set__name", "sort_order", "title")
    if palette_set_id is not None:
        qs = qs.filter(palette_set_id=palette_set_id)
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    items = [palette_summary(p) for p in qs]
    return {"palettes": items, "total": len(items)}


@router.post(
    "/",
    response={201: PaletteSummary, 400: Error, 404: Error, 409: Error},
    summary="Create a palette",
)
def create_palette(request: HttpRequest, response: HttpResponse, payload: PaletteCreate):
    from phoxtail.design.models import Palette, PaletteSet

    try:
        ps = PaletteSet.objects.get(pk=payload.palette_set_id)
    except PaletteSet.DoesNotExist:
        raise HttpError(404, f"PaletteSet {payload.palette_set_id} not found.")

    data = payload.model_dump()
    data.pop("palette_set_id")
    try:
        palette = Palette.objects.create(palette_set=ps, **data)
    except IntegrityError:
        raise HttpError(
            409,
            f"A palette named '{payload.title}' already exists in this palette set.",
        )

    palette.palette_set = ps
    response["ETag"] = palette_etag(palette)
    return 201, palette_summary(palette)


@router.get(
    "/{palette_id}/",
    response={200: PaletteSummary, 404: Error},
    summary="Get a palette",
)
def get_palette(request: HttpRequest, response: HttpResponse, palette_id: int):
    p = resolve_palette(palette_id)
    response["ETag"] = palette_etag(p)
    return palette_summary(p)


@router.patch(
    "/{palette_id}/",
    response={
        200: PaletteSummary,
        400: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a palette",
)
def patch_palette(
    request: HttpRequest,
    response: HttpResponse,
    palette_id: int,
    payload: PalettePatch,
):
    p = resolve_palette(palette_id)
    require_if_match(request, palette_etag(p))

    data = payload.model_dump(exclude_unset=True)

    if "palette_set_id" in data:
        from phoxtail.design.models import PaletteSet

        try:
            p.palette_set = PaletteSet.objects.get(pk=data.pop("palette_set_id"))
        except PaletteSet.DoesNotExist:
            raise HttpError(404, f"PaletteSet {data['palette_set_id']} not found.")

    for field, value in data.items():
        setattr(p, field, value)

    try:
        p.save()
    except IntegrityError:
        raise HttpError(409, "A palette with that title already exists in this palette set.")

    p.refresh_from_db()
    response["ETag"] = palette_etag(p)
    return palette_summary(p)


@router.delete(
    "/{palette_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a palette",
)
def delete_palette(request: HttpRequest, palette_id: int):
    p = resolve_palette(palette_id)
    require_if_match(request, palette_etag(p))
    p.delete()
    return 204, None
