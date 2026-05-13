"""``/api/cms/v1/site-settings/{site_id}/fonts/`` — SiteSettingFont CRUD.

Endpoints:
- GET    /              — list font assignments for a site
- POST   /              — add a font assignment
- GET    /{id}/         — get one assignment, sets ETag
- PATCH  /{id}/         — update (requires If-Match)
- DELETE /{id}/         — remove (requires If-Match)
"""

from __future__ import annotations

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

from phoxtail.cms.api.v1._helpers import (
    require_if_match,
    resolve_setting,
    resolve_site_font,
    serialize_site_font,
    site_setting_font_etag,
)

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SiteSettingFontItem(Schema):
    id: int
    font_family_id: int
    font_family_name: str
    role_id: int
    role_name: str
    role_identifier: str
    sort_order: int


class SiteSettingFontList(Schema):
    fonts: list[SiteSettingFontItem]
    total: int


class SiteSettingFontCreate(Schema):
    font_family_id: int
    role_id: int
    sort_order: int = 0


class SiteSettingFontPatch(Schema):
    font_family_id: int | None = None
    role_id: int | None = None
    sort_order: int | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{site_id}/fonts/",
    response={200: SiteSettingFontList, 404: Error},
    summary="List font assignments for a site",
)
def list_site_fonts(request: HttpRequest, site_id: int):
    from phoxtail.cms.models import SiteSettingFont

    setting = resolve_setting(site_id)
    qs = SiteSettingFont.objects.select_related("font_family", "role").filter(config=setting).order_by("sort_order")
    items = [serialize_site_font(sf) for sf in qs]
    return {"fonts": items, "total": len(items)}


@router.post(
    "/{site_id}/fonts/",
    response={201: SiteSettingFontItem, 400: Error, 404: Error, 409: Error},
    summary="Add a font assignment to a site",
)
def create_site_font(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    payload: SiteSettingFontCreate,
):
    from phoxtail.cms.models import SiteSettingFont
    from phoxtail.design.models import FontFamily, FontRole

    setting = resolve_setting(site_id)

    try:
        FontFamily.objects.get(pk=payload.font_family_id)
    except FontFamily.DoesNotExist:
        raise HttpError(400, f"FontFamily {payload.font_family_id} not found.")

    try:
        FontRole.objects.get(pk=payload.role_id)
    except FontRole.DoesNotExist:
        raise HttpError(400, f"FontRole {payload.role_id} not found.")

    try:
        sf = SiteSettingFont.objects.create(
            config=setting,
            font_family_id=payload.font_family_id,
            role_id=payload.role_id,
            sort_order=payload.sort_order,
        )
    except IntegrityError:
        raise HttpError(
            409,
            f"A font assignment for role {payload.role_id} already exists on this site.",
        )

    sf = SiteSettingFont.objects.select_related("font_family", "role").get(pk=sf.pk)
    response["ETag"] = site_setting_font_etag(sf)
    return 201, serialize_site_font(sf)


@router.get(
    "/{site_id}/fonts/{font_id}/",
    response={200: SiteSettingFontItem, 404: Error},
    summary="Get a font assignment",
)
def get_site_font(request: HttpRequest, response: HttpResponse, site_id: int, font_id: int):
    _, sf = resolve_site_font(site_id, font_id)
    response["ETag"] = site_setting_font_etag(sf)
    return serialize_site_font(sf)


@router.patch(
    "/{site_id}/fonts/{font_id}/",
    response={
        200: SiteSettingFontItem,
        400: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a font assignment",
)
def patch_site_font(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    font_id: int,
    payload: SiteSettingFontPatch,
):
    from phoxtail.design.models import FontFamily, FontRole

    _, sf = resolve_site_font(site_id, font_id)
    require_if_match(request, site_setting_font_etag(sf))

    data = payload.model_dump(exclude_unset=True)

    if "font_family_id" in data:
        try:
            FontFamily.objects.get(pk=data["font_family_id"])
        except FontFamily.DoesNotExist:
            raise HttpError(400, f"FontFamily {data['font_family_id']} not found.")

    if "role_id" in data:
        try:
            FontRole.objects.get(pk=data["role_id"])
        except FontRole.DoesNotExist:
            raise HttpError(400, f"FontRole {data['role_id']} not found.")

    for field, value in data.items():
        setattr(sf, field, value)

    try:
        sf.save()
    except IntegrityError:
        raise HttpError(
            409,
            "A font assignment for that role already exists on this site.",
        )

    sf = type(sf).objects.select_related("font_family", "role").get(pk=sf.pk)
    response["ETag"] = site_setting_font_etag(sf)
    return serialize_site_font(sf)


@router.delete(
    "/{site_id}/fonts/{font_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Remove a font assignment",
)
def delete_site_font(request: HttpRequest, site_id: int, font_id: int):
    _, sf = resolve_site_font(site_id, font_id)
    require_if_match(request, site_setting_font_etag(sf))
    sf.delete()
    return 204, None
