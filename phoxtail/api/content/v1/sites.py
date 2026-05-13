"""``/api/content/v1/sites/`` — Wagtail Site CRUD endpoints.

Endpoints:
- GET    /           — list all sites
- POST   /           — create a site
- GET    /{id}/      — detail, sets ETag
- PATCH  /{id}/      — update fields (requires If-Match)
- DELETE /{id}/      — delete (requires If-Match)

ETags are computed by hashing all five writable fields. This is
deterministic (same values → same tag, stable across restarts) and
correct for config objects that have no revision timestamp.
"""

from __future__ import annotations

import hashlib

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

router = Router()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SiteSummary(Schema):
    id: int
    hostname: str
    port: int
    site_name: str
    root_page_id: int
    is_default_site: bool
    root_url: str


class SiteList(Schema):
    sites: list[SiteSummary]
    total: int


class SiteCreate(Schema):
    hostname: str
    port: int = 80
    site_name: str = ""
    root_page_id: int
    is_default_site: bool = False


class SitePatch(Schema):
    hostname: str | None = None
    port: int | None = None
    site_name: str | None = None
    root_page_id: int | None = None
    is_default_site: bool | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# ETag helpers
# ---------------------------------------------------------------------------


def site_etag(site) -> str:
    """Weak ETag derived from all five writable fields.

    Hash-based rather than timestamp-based because Site has no revision
    history. Deterministic: same field values always produce the same tag.
    """
    h = hashlib.sha256()
    for part in [
        str(site.pk),
        site.hostname,
        str(site.port),
        site.site_name,
        str(site.root_page_id),
        "1" if site.is_default_site else "0",
    ]:
        h.update(part.encode())
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def _strip_weak(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


def _etag_matches(header_value: str | None, current: str) -> bool:
    if not header_value:
        return False
    candidates = {t.strip() for t in header_value.split(",")}
    return "*" in candidates or _strip_weak(current) in {_strip_weak(t) for t in candidates}


def _require_if_match(request: HttpRequest, site) -> None:
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this site.",
        )
    if not _etag_matches(if_match, site_etag(site)):
        raise HttpError(
            412,
            "ETag mismatch: the site has changed since you last read it. Re-fetch and retry.",
        )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize(s) -> dict:
    return {
        "id": s.pk,
        "hostname": s.hostname,
        "port": s.port,
        "site_name": s.site_name,
        "root_page_id": s.root_page_id,
        "is_default_site": s.is_default_site,
        "root_url": s.root_url,
    }


def _resolve_site(site_id: int):
    from wagtail.models import Site

    try:
        return Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        raise HttpError(404, f"Site {site_id} not found.")


def _apply_and_save(site, data: dict) -> None:
    """Apply a dict of updates, full_clean, save — shared by create and patch."""
    from wagtail.models import Page

    if "root_page_id" in data:
        root_page_id = data.pop("root_page_id")
        try:
            site.root_page = Page.objects.get(pk=root_page_id)
        except Page.DoesNotExist:
            raise HttpError(400, f"Page {root_page_id} not found.")
    for field, value in data.items():
        setattr(site, field, value)

    try:
        site.full_clean()
    except DjangoValidationError as exc:
        if hasattr(exc, "message_dict") and "is_default_site" in exc.message_dict:
            raise HttpError(409, exc.message_dict["is_default_site"][0])
        raise HttpError(400, "; ".join(exc.messages))

    try:
        site.save()
    except IntegrityError:
        raise HttpError(
            409,
            f"A site already exists with hostname '{site.hostname}' and port {site.port}.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response={200: SiteList}, summary="List sites")
def list_sites(request: HttpRequest):
    from wagtail.models import Site

    qs = Site.objects.all().order_by("hostname")
    sites = [_serialize(s) for s in qs]
    return {"sites": sites, "total": len(sites)}


@router.post(
    "/",
    response={201: SiteSummary, 400: Error, 403: Error, 409: Error},
    summary="Create a Wagtail site",
)
def create_site(request: HttpRequest, response: HttpResponse, payload: SiteCreate):
    from wagtail.models import Site

    if not request.auth.has_perm("wagtailcore.add_site"):
        raise HttpError(403, "User does not have permission to create sites.")

    data = payload.model_dump()
    site = Site()
    _apply_and_save(site, data)
    response["ETag"] = site_etag(site)
    return 201, _serialize(site)


@router.get(
    "/{site_id}/",
    response={200: SiteSummary, 404: Error},
    summary="Get a site",
)
def get_site(request: HttpRequest, response: HttpResponse, site_id: int):
    site = _resolve_site(site_id)
    response["ETag"] = site_etag(site)
    return _serialize(site)


@router.patch(
    "/{site_id}/",
    response={
        200: SiteSummary,
        400: Error,
        403: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a site's fields",
)
def patch_site(
    request: HttpRequest,
    response: HttpResponse,
    site_id: int,
    payload: SitePatch,
):
    if not request.auth.has_perm("wagtailcore.change_site"):
        raise HttpError(403, "User does not have permission to change sites.")

    site = _resolve_site(site_id)
    _require_if_match(request, site)

    data = payload.model_dump(exclude_unset=True)
    _apply_and_save(site, data)
    response["ETag"] = site_etag(site)
    return _serialize(site)


@router.delete(
    "/{site_id}/",
    response={204: None, 403: Error, 404: Error, 412: Error, 428: Error},
    summary="Delete a site",
)
def delete_site(request: HttpRequest, site_id: int):
    if not request.auth.has_perm("wagtailcore.delete_site"):
        raise HttpError(403, "User does not have permission to delete sites.")

    site = _resolve_site(site_id)
    _require_if_match(request, site)
    site.delete()
    return 204, None
