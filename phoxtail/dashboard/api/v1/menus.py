"""``/api/dashboard/v1/menus`` — dashboard menu endpoints."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError

from phoxtail.api.auth import guarded
from phoxtail.dashboard.api.v1.schemas import (
    Error,
    Menu,
    MenuCreate,
    MenuList,
    MenuUpdate,
)
from phoxtail.dashboard.models import Menu as MenuModel

router = Router()


def _summary(menu: MenuModel) -> dict:
    return {
        "id": menu.id,
        "uuid": str(menu.uuid),
        "site_id": menu.site_id,
        "site_hostname": menu.site.hostname,
        "locale_id": menu.locale_id,
        "language_code": menu.locale.language_code,
        "entry_count": len(menu.items),
        "created_at": menu.created_at.isoformat(),
        "updated_at": menu.updated_at.isoformat(),
    }


def _detail(menu: MenuModel) -> dict:
    return {**_summary(menu), "items": json.dumps(menu.items.get_prep_value() or [], indent=2)}


def _etag(menu: MenuModel) -> str:
    h = hashlib.sha256()
    for part in (
        str(menu.site_id),
        str(menu.locale_id),
        json.dumps(menu.items.get_prep_value() or [], sort_keys=True),
        menu.updated_at.isoformat(),
    ):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def _strip_weak_prefix(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


def _etag_matches(header_value: str | None, current: str) -> bool:
    if not header_value:
        return False
    candidates = {tag.strip() for tag in header_value.split(",")}
    normalized = {_strip_weak_prefix(tag) for tag in candidates}
    return _strip_weak_prefix(current) in normalized or "*" in candidates


def _resolve(menu_uuid: UUID) -> MenuModel:
    try:
        return MenuModel.objects.select_related("site", "locale").get(uuid=menu_uuid)
    except MenuModel.DoesNotExist as exc:
        raise HttpError(404, f"Menu {menu_uuid} not found.") from exc


def _resolve_site(pk: int):
    from wagtail.models import Site

    try:
        return Site.objects.get(pk=pk)
    except Site.DoesNotExist as exc:
        raise HttpError(404, f"Site {pk} not found.") from exc


def _resolve_locale(pk: int):
    from wagtail.models import Locale

    try:
        return Locale.objects.get(pk=pk)
    except Locale.DoesNotExist as exc:
        raise HttpError(404, f"Locale {pk} not found.") from exc


def _reject_unknown_entries(items) -> None:
    """Refuse an entry type the stream does not define.

    Wagtail drops an entry whose type it cannot resolve, so a typo would
    otherwise answer 200 with a menu that had quietly lost it.
    """
    from phoxtail.dashboard.blocks import MenuStreamBlock

    stream = MenuStreamBlock()
    top = set(stream.child_blocks)
    nested = set(stream.child_blocks["dropdown"].child_blocks["items"].child_blocks)

    unknown = []
    for index, entry in enumerate(items or []):
        entry_type = entry.get("type") if isinstance(entry, dict) else None
        if entry_type not in top:
            unknown.append(f"items[{index}]: unknown entry type {entry_type!r}")
            continue
        if entry_type == "dropdown":
            inner = (entry.get("value") or {}).get("items") or []
            for position, item in enumerate(inner):
                item_type = item.get("type") if isinstance(item, dict) else None
                if item_type not in nested:
                    unknown.append(f"items[{index}].items[{position}]: unknown entry type {item_type!r}")

    if unknown:
        raise HttpError(422, "; ".join(unknown) + f". Known types: {', '.join(sorted(top))}.")


def _format_validation_error(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{k}: {', '.join(v)}" if isinstance(v, list) else f"{k}: {v}" for k, v in exc.message_dict.items()
        )
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)


@router.get(
    "/",
    response={200: MenuList, 403: Error},
    auth=guarded("phoxtail_dashboard.view_menu"),
    summary="List dashboard menus",
)
def list_menus(
    request: HttpRequest,
    site: int | None = Query(None, description="Filter by site ID."),
    locale: int | None = Query(None, description="Filter by locale ID."),
):
    qs = MenuModel.objects.select_related("site", "locale").order_by("site__hostname", "locale__language_code")
    if site is not None:
        qs = qs.filter(site_id=site)
    if locale is not None:
        qs = qs.filter(locale_id=locale)
    menus = [_summary(menu) for menu in qs]
    return {"menus": menus, "total": len(menus)}


@router.get(
    "/{menu_uuid}/",
    response={200: Menu, 403: Error, 404: Error},
    auth=guarded("phoxtail_dashboard.view_menu"),
    summary="Show a dashboard menu",
)
def get_menu(request: HttpRequest, response: HttpResponse, menu_uuid: UUID):
    menu = _resolve(menu_uuid)
    response["ETag"] = _etag(menu)
    return _detail(menu)


@router.post(
    "/",
    response={201: Menu, 403: Error, 422: Error, 404: Error, 409: Error},
    auth=guarded("phoxtail_dashboard.add_menu"),
    summary="Create a dashboard menu",
)
def create_menu(request: HttpRequest, response: HttpResponse, payload: MenuCreate):
    site = _resolve_site(payload.site_id)
    locale = _resolve_locale(payload.locale_id)

    # Asked before validating: full_clean() checks the constraint too, but
    # reports it as a field error, and a second menu for a site and language
    # is a conflict rather than a malformed request.
    if MenuModel.objects.filter(site=site, locale=locale).exists():
        raise HttpError(409, f"A menu for site {payload.site_id} in locale {payload.locale_id} already exists.")

    menu = MenuModel(site=site, locale=locale)
    if payload.items:
        _reject_unknown_entries(payload.items)
        # A StreamField accepts raw stream data on assignment and converts
        # it; the descriptor advertises only the converted type.
        menu.items = payload.items  # type: ignore[assignment]

    try:
        menu.full_clean()
    except ValidationError as exc:
        raise HttpError(422, _format_validation_error(exc))

    try:
        menu.save()
    except IntegrityError:
        # Two writers racing past the check above.
        raise HttpError(
            409,
            f"A menu for site {payload.site_id} in locale {payload.locale_id} already exists.",
        )

    menu = _resolve(menu.uuid)
    response["ETag"] = _etag(menu)
    return 201, _detail(menu)


@router.patch(
    "/{menu_uuid}/",
    response={200: Menu, 403: Error, 422: Error, 404: Error, 412: Error, 428: Error},
    auth=guarded("phoxtail_dashboard.change_menu"),
    summary="Update a dashboard menu's entries",
)
def update_menu(request: HttpRequest, response: HttpResponse, menu_uuid: UUID, payload: MenuUpdate):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this menu.",
        )

    menu = _resolve(menu_uuid)
    if not _etag_matches(if_match, _etag(menu)):
        raise HttpError(
            412,
            "ETag mismatch: the menu has changed since you last read it. Re-fetch and retry.",
        )

    if payload.items is not None:
        _reject_unknown_entries(payload.items)
        menu.items = payload.items  # type: ignore[assignment]

    try:
        menu.full_clean()
    except ValidationError as exc:
        raise HttpError(422, _format_validation_error(exc))

    menu.save()

    menu = _resolve(menu_uuid)
    response["ETag"] = _etag(menu)
    return _detail(menu)


@router.delete(
    "/{menu_uuid}/",
    response={204: None, 403: Error, 404: Error},
    auth=guarded("phoxtail_dashboard.delete_menu"),
    summary="Delete a dashboard menu",
)
def delete_menu(request: HttpRequest, menu_uuid: UUID):
    menu = _resolve(menu_uuid)
    menu.delete()
    return 204, None
