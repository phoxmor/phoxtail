"""``/api/cms/v1/site-settings/{site_id}/palettes/`` — SiteSettingPalette CRUD.

Endpoints:
- GET    /              — list palette assignments for a site
- POST   /              — add a palette assignment
- GET    /{id}/         — get one assignment, sets ETag
- PATCH  /{id}/         — update (requires If-Match)
- DELETE /{id}/         — remove (requires If-Match)
"""

from __future__ import annotations

from django.db import IntegrityError
from django.db.models import Max
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

from phoxtail.cms.api.v1._helpers import (
    require_if_match,
    resolve_setting,
    resolve_site_palette,
    serialize_site_palette,
    site_setting_palette_etag,
)

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SiteSettingPaletteItem(Schema):
    id: int
    palette_id: int
    palette_title: str
    role_id: int
    role_name: str
    role_identifier: str
    sort_order: int


class SiteSettingPaletteList(Schema):
    palettes: list[SiteSettingPaletteItem]
    total: int


class SiteSettingPaletteCreate(Schema):
    palette_id: int
    role_id: int
    sort_order: int | None = None


class SiteSettingPalettePatch(Schema):
    palette_id: int | None = None
    role_id: int | None = None
    sort_order: int | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{site_id}/palettes/",
    response={200: SiteSettingPaletteList, 404: Error},
    summary="List palette assignments for a site",
)
def list_site_palettes(request: HttpRequest, site_id: int):
    from phoxtail.cms.models import SiteSettingPalette

    setting = resolve_setting(site_id)
    qs = SiteSettingPalette.objects.select_related("palette", "role").filter(config=setting).order_by("sort_order")
    items = [serialize_site_palette(sp) for sp in qs]
    return {"palettes": items, "total": len(items)}


@router.post(
    "/{site_id}/palettes/",
    response={201: SiteSettingPaletteItem, 400: Error, 404: Error, 409: Error},
    summary="Add a palette assignment to a site",
)
def create_site_palette(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    payload: SiteSettingPaletteCreate,
):
    from phoxtail.cms.models import SiteSettingPalette
    from phoxtail.design.models import Palette, PaletteRole

    setting = resolve_setting(site_id)

    try:
        Palette.objects.get(pk=payload.palette_id)
    except Palette.DoesNotExist:
        raise HttpError(400, f"Palette {payload.palette_id} not found.")

    try:
        PaletteRole.objects.get(pk=payload.role_id)
    except PaletteRole.DoesNotExist:
        raise HttpError(400, f"PaletteRole {payload.role_id} not found.")

    if payload.sort_order is None:
        agg = SiteSettingPalette.objects.filter(config=setting).aggregate(max=Max("sort_order"))
        sort_order = (agg["max"] or 0) + 1
    else:
        sort_order = payload.sort_order

    try:
        sp = SiteSettingPalette.objects.create(
            config=setting,
            palette_id=payload.palette_id,
            role_id=payload.role_id,
            sort_order=sort_order,
        )
    except IntegrityError:
        raise HttpError(
            409,
            f"A palette assignment for role {payload.role_id} already exists on this site.",
        )

    sp = SiteSettingPalette.objects.select_related("palette", "role").get(pk=sp.pk)
    response["ETag"] = site_setting_palette_etag(sp)
    return 201, serialize_site_palette(sp)


@router.get(
    "/{site_id}/palettes/{palette_id}/",
    response={200: SiteSettingPaletteItem, 404: Error},
    summary="Get a palette assignment",
)
def get_site_palette(request: HttpRequest, response: HttpResponse, site_id: int, palette_id: int):
    _, sp = resolve_site_palette(site_id, palette_id)
    response["ETag"] = site_setting_palette_etag(sp)
    return serialize_site_palette(sp)


@router.patch(
    "/{site_id}/palettes/{palette_id}/",
    response={
        200: SiteSettingPaletteItem,
        400: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a palette assignment",
)
def patch_site_palette(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    palette_id: int,
    payload: SiteSettingPalettePatch,
):
    from phoxtail.design.models import Palette, PaletteRole

    _, sp = resolve_site_palette(site_id, palette_id)
    require_if_match(request, site_setting_palette_etag(sp))

    data = payload.model_dump(exclude_unset=True)

    if "palette_id" in data:
        try:
            Palette.objects.get(pk=data["palette_id"])
        except Palette.DoesNotExist:
            raise HttpError(400, f"Palette {data['palette_id']} not found.")

    if "role_id" in data:
        try:
            PaletteRole.objects.get(pk=data["role_id"])
        except PaletteRole.DoesNotExist:
            raise HttpError(400, f"PaletteRole {data['role_id']} not found.")

    for field, value in data.items():
        setattr(sp, field, value)

    try:
        sp.save()
    except IntegrityError:
        raise HttpError(
            409,
            "A palette assignment for that role already exists on this site.",
        )

    sp = type(sp).objects.select_related("palette", "role").get(pk=sp.pk)
    response["ETag"] = site_setting_palette_etag(sp)
    return serialize_site_palette(sp)


@router.delete(
    "/{site_id}/palettes/{palette_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Remove a palette assignment",
)
def delete_site_palette(request: HttpRequest, site_id: int, palette_id: int):
    _, sp = resolve_site_palette(site_id, palette_id)
    require_if_match(request, site_setting_palette_etag(sp))
    sp.delete()
    return 204, None
