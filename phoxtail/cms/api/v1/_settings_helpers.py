"""Resolution, serialization and ETag helpers for the site-settings endpoints.

Distinct from ``_helpers``, which serves the pages endpoints: the two disagree
about what ``require_if_match`` takes — a page it can hash itself, or an ETag
it is handed — so they stay apart.
"""

from __future__ import annotations

import hashlib

from ninja.errors import HttpError


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def _strip_weak(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


def etag_matches(header_value: str | None, current: str) -> bool:
    if not header_value:
        return False
    candidates = {t.strip() for t in header_value.split(",")}
    return "*" in candidates or _strip_weak(current) in {_strip_weak(t) for t in candidates}


def require_if_match(request, current_etag: str) -> None:
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Fetch the resource first and pass the ETag from the response.",
        )
    if not etag_matches(if_match, current_etag):
        raise HttpError(
            412,
            "ETag mismatch: the resource has changed since you last read it. Re-fetch and retry.",
        )


def site_setting_etag(setting) -> str:
    return _hash(
        str(setting.site_id),
        str(setting.logo_id or ""),
        str(setting.logo_dark_id or ""),
        str(setting.favicon_id or ""),
        str(setting.favicon_dark_id or ""),
        str(setting.og_image_id or ""),
        str(setting.og_image_dark_id or ""),
        str(setting.logo_admin_id or ""),
        str(setting.logo_admin_dark_id or ""),
        str(setting.symbol_admin_id or ""),
        str(setting.symbol_admin_dark_id or ""),
    )


def site_setting_font_etag(sf) -> str:
    return _hash(
        str(sf.pk),
        str(sf.config_id),
        str(sf.font_family_id),
        str(sf.role_id),
        str(sf.sort_order or 0),
    )


def site_setting_palette_etag(sp) -> str:
    return _hash(
        str(sp.pk),
        str(sp.config_id),
        str(sp.palette_id),
        str(sp.role_id),
        str(sp.sort_order or 0),
    )


def resolve_site(site_id: int):
    from wagtail.models import Site

    try:
        return Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        raise HttpError(404, f"Site {site_id} not found.")


def resolve_setting(site_id: int):
    from phoxtail.cms.models import SiteSetting

    site = resolve_site(site_id)
    return SiteSetting.for_site(site)


def resolve_site_font(site_id: int, font_id: int):
    from phoxtail.cms.models import SiteSettingFont

    setting = resolve_setting(site_id)
    try:
        sf = SiteSettingFont.objects.select_related("font_family", "role").get(pk=font_id, config=setting)
        return setting, sf
    except SiteSettingFont.DoesNotExist:
        raise HttpError(404, f"SiteSettingFont {font_id} not found for site {site_id}.")


def resolve_site_palette(site_id: int, palette_id: int):
    from phoxtail.cms.models import SiteSettingPalette

    setting = resolve_setting(site_id)
    try:
        sp = SiteSettingPalette.objects.select_related("palette", "role").get(pk=palette_id, config=setting)
        return setting, sp
    except SiteSettingPalette.DoesNotExist:
        raise HttpError(404, f"SiteSettingPalette {palette_id} not found for site {site_id}.")


def serialize_setting(s) -> dict:
    return {
        "site_id": s.site_id,
        "logo_id": s.logo_id,
        "logo_dark_id": s.logo_dark_id,
        "favicon_id": s.favicon_id,
        "favicon_dark_id": s.favicon_dark_id,
        "og_image_id": s.og_image_id,
        "og_image_dark_id": s.og_image_dark_id,
        "logo_admin_id": s.logo_admin_id,
        "logo_admin_dark_id": s.logo_admin_dark_id,
        "symbol_admin_id": s.symbol_admin_id,
        "symbol_admin_dark_id": s.symbol_admin_dark_id,
    }


def serialize_site_font(sf) -> dict:
    return {
        "id": sf.pk,
        "font_family_id": sf.font_family_id,
        "font_family_name": sf.font_family.name,
        "role_id": sf.role_id,
        "role_name": sf.role.name,
        "role_identifier": sf.role.identifier,
        "sort_order": sf.sort_order or 0,
    }


def serialize_site_palette(sp) -> dict:
    return {
        "id": sp.pk,
        "palette_id": sp.palette_id,
        "palette_title": sp.palette.title,
        "role_id": sp.role_id,
        "role_name": sp.role.name,
        "role_identifier": sp.role.identifier,
        "sort_order": sp.sort_order or 0,
    }
