"""``/api/cms/v1/site-settings/{site_id}/`` — SiteSetting read/update.

SiteSetting is a singleton per Wagtail Site (one-per-site). There is no
create or delete — GET auto-creates a blank record if none exists yet.

Endpoints:
- GET   /{site_id}/   — get (or auto-create) settings for a site, sets ETag
- PATCH /{site_id}/   — update image fields (requires If-Match)
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

from phoxtail.cms.api.v1._settings_helpers import (
    require_if_match,
    resolve_setting,
    serialize_setting,
    site_setting_etag,
)

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SiteSettingDetail(Schema):
    site_id: int
    logo_id: int | None
    logo_dark_id: int | None
    favicon_id: int | None
    favicon_dark_id: int | None
    og_image_id: int | None
    og_image_dark_id: int | None
    logo_admin_id: int | None
    logo_admin_dark_id: int | None
    symbol_admin_id: int | None
    symbol_admin_dark_id: int | None


class SiteSettingPatch(Schema):
    logo_id: int | None = None
    logo_dark_id: int | None = None
    favicon_id: int | None = None
    favicon_dark_id: int | None = None
    og_image_id: int | None = None
    og_image_dark_id: int | None = None
    logo_admin_id: int | None = None
    logo_admin_dark_id: int | None = None
    symbol_admin_id: int | None = None
    symbol_admin_dark_id: int | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Image FK fields on the model
# ---------------------------------------------------------------------------

_IMAGE_FIELDS = (
    "logo_id",
    "logo_dark_id",
    "favicon_id",
    "favicon_dark_id",
    "og_image_id",
    "og_image_dark_id",
    "logo_admin_id",
    "logo_admin_dark_id",
    "symbol_admin_id",
    "symbol_admin_dark_id",
)


def _validate_image_ids(data: dict) -> None:
    """Raise 400 for any image FK that refers to a non-existent image."""
    from wagtail.images import get_image_model

    image_ids = [v for k, v in data.items() if k in _IMAGE_FIELDS and v is not None]
    if not image_ids:
        return
    Image = get_image_model()
    found = set(Image.objects.filter(pk__in=image_ids).values_list("pk", flat=True))
    missing = set(image_ids) - found
    if missing:
        raise HttpError(400, f"Image(s) not found: {sorted(missing)}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{site_id}/",
    response={200: SiteSettingDetail, 404: Error},
    summary="Get site settings",
)
def get_site_setting(request: HttpRequest, response: HttpResponse, site_id: int):
    setting = resolve_setting(site_id)
    response["ETag"] = site_setting_etag(setting)
    return serialize_setting(setting)


@router.patch(
    "/{site_id}/",
    response={
        200: SiteSettingDetail,
        400: Error,
        404: Error,
        412: Error,
        428: Error,
    },
    summary="Update site branding images",
)
def patch_site_setting(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    payload: SiteSettingPatch,
):
    setting = resolve_setting(site_id)
    require_if_match(request, site_setting_etag(setting))

    data = payload.model_dump(exclude_unset=True)
    _validate_image_ids(data)
    for field, value in data.items():
        setattr(setting, field, value)
    setting.save()

    response["ETag"] = site_setting_etag(setting)
    return serialize_setting(setting)
