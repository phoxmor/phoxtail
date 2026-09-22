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
from django.db.models import Max
from django.http import HttpRequest, HttpResponse
from ninja import Schema
from ninja.errors import HttpError

from phoxtail.api.auth import scoped
from phoxtail.api.pagination import Router
from phoxtail.cms.api.v1._permissions import require_settings_access
from phoxtail.cms.api.v1._settings_helpers import (
    require_if_match,
    resolve_setting,
    resolve_site_font,
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

    @staticmethod
    def resolve_font_family_name(row) -> str:
        return row.font_family.name

    @staticmethod
    def resolve_role_name(row) -> str:
        return row.role.name

    @staticmethod
    def resolve_role_identifier(row) -> str:
        return row.role.identifier

    @staticmethod
    def resolve_sort_order(row) -> int:
        return row.sort_order or 0


class SiteSettingFontCreate(Schema):
    font_family_id: int
    role_id: int
    sort_order: int | None = None


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
    response={200: list[SiteSettingFontItem], 404: Error},
    summary="List font assignments for a site",
    auth=scoped("phoxtail_cms.view_sitesetting"),
)
def list_site_fonts(request: HttpRequest, site_id: int):
    from phoxtail.cms.models import SiteSettingFont

    setting = resolve_setting(site_id)
    require_settings_access(request.auth.user, setting)
    return SiteSettingFont.objects.select_related("font_family", "role").filter(config=setting).order_by("sort_order")


@router.post(
    "/{site_id}/fonts/",
    response={201: SiteSettingFontItem, 400: Error, 404: Error, 409: Error},
    summary="Add a font assignment to a site",
    auth=scoped("phoxtail_cms.change_sitesetting"),
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
    require_settings_access(request.auth.user, setting)

    try:
        FontFamily.objects.get(pk=payload.font_family_id)
    except FontFamily.DoesNotExist:
        raise HttpError(400, f"FontFamily {payload.font_family_id} not found.")

    try:
        FontRole.objects.get(pk=payload.role_id)
    except FontRole.DoesNotExist:
        raise HttpError(400, f"FontRole {payload.role_id} not found.")

    if payload.sort_order is None:
        agg = SiteSettingFont.objects.filter(config=setting).aggregate(max=Max("sort_order"))
        sort_order = (agg["max"] or 0) + 1
    else:
        sort_order = payload.sort_order

    try:
        sf = SiteSettingFont.objects.create(
            config=setting,
            font_family_id=payload.font_family_id,
            role_id=payload.role_id,
            sort_order=sort_order,
        )
    except IntegrityError:
        raise HttpError(
            409,
            f"A font assignment for role {payload.role_id} already exists on this site.",
        )

    sf = SiteSettingFont.objects.select_related("font_family", "role").get(pk=sf.pk)
    response["ETag"] = site_setting_font_etag(sf)
    return 201, sf


@router.get(
    "/{site_id}/fonts/{font_id}/",
    response={200: SiteSettingFontItem, 404: Error},
    summary="Get a font assignment",
    auth=scoped("phoxtail_cms.view_sitesetting"),
)
def get_site_font(request: HttpRequest, response: HttpResponse, site_id: int, font_id: int):
    setting, sf = resolve_site_font(site_id, font_id)
    require_settings_access(request.auth.user, setting)
    response["ETag"] = site_setting_font_etag(sf)
    return sf


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
    auth=scoped("phoxtail_cms.change_sitesetting"),
)
def patch_site_font(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    font_id: int,
    payload: SiteSettingFontPatch,
):
    from phoxtail.design.models import FontFamily, FontRole

    setting, sf = resolve_site_font(site_id, font_id)
    require_settings_access(request.auth.user, setting)
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
    return sf


@router.delete(
    "/{site_id}/fonts/{font_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Remove a font assignment",
    auth=scoped("phoxtail_cms.change_sitesetting"),
)
def delete_site_font(request: HttpRequest, site_id: int, font_id: int):
    setting, sf = resolve_site_font(site_id, font_id)
    require_settings_access(request.auth.user, setting)
    require_if_match(request, site_setting_font_etag(sf))
    sf.delete()
    return 204, None
