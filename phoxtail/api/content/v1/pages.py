"""``/api/content/v1/pages/`` — generic Wagtail Page endpoints.

Endpoints:
- ``GET    /``    — list pages (?type, ?parent, ?live, ?search, ?locale, ?site)
- ``GET    /{page_id}/``          — detail, sets ETag
- ``PATCH  /{page_id}/``          — scalar fields (common + contributed)
- ``POST   /{page_id}/publish/``  — publish the latest draft revision
- ``POST   /{page_id}/unpublish/``— take the page offline

Per-page-type scalar fields are applied via
``PageSchemaContribution.apply_patch``. The core endpoint only knows
about the common Wagtail fields.
"""

from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError
from wagtail.models import Page

from phoxtail.api.content.v1._helpers import (
    apply_common_patch,
    apply_contributed_patch,
    filter_by_content_type,
    page_etag,
    require_edit_permission,
    require_if_match,
    require_publish_permission,
    resolve_page,
    resolve_page_for_read,
    serialize_page_detail,
    serialize_page_summary,
)
from phoxtail.api.content.v1.schemas import (
    BodyResponse,  # noqa: F401 — re-exported for Ninja docs
    Error,
    PageDetail,
    PageList,
    PagePatch,
)

router = Router()


@router.get(
    "/",
    response={200: PageList, 400: Error, 404: Error},
    summary="List pages",
)
def list_pages(
    request: HttpRequest,
    type: str | None = Query(
        None,
        description="Filter by content type, e.g. 'phoxtail_blog.BlogPostPage'.",
    ),
    parent: int | None = Query(None, description="Filter by parent page ID."),
    live: bool | None = Query(None, description="Filter by live status."),
    search: str | None = Query(
        None, description="Autocomplete prefix search on title."
    ),
    locale: str | None = Query(
        None, description="Filter by locale language code, e.g. 'en'."
    ),
    site: int | None = Query(None, description="Filter by site ID."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    qs = Page.objects.all().order_by("path")
    if type:
        qs = filter_by_content_type(qs, type)
    if parent is not None:
        qs = qs.child_of(_get_parent_page(parent))
    if live is not None:
        qs = qs.filter(live=live)
    if locale:
        qs = _filter_by_locale(qs, locale)
    if site is not None:
        qs = _filter_by_site(qs, site)
    if search:
        qs = qs.autocomplete(search)

    total = qs.count()
    page_slice = qs[offset : offset + limit]
    # Downcast each to its specific subclass so content_type resolves correctly.
    pages = [serialize_page_summary(p.specific) for p in page_slice]
    return {"pages": pages, "total": total}


def _filter_by_locale(qs, language_code: str):
    from wagtail.models import Locale

    try:
        locale = Locale.objects.get(language_code=language_code)
    except Locale.DoesNotExist as exc:
        raise HttpError(400, f"Unknown locale: '{language_code}'.") from exc
    return qs.filter(locale=locale)


def _filter_by_site(qs, site_pk: int):
    from wagtail.models import Site

    try:
        site = Site.objects.get(pk=site_pk)
    except Site.DoesNotExist as exc:
        raise HttpError(400, f"Site {site_pk} not found.") from exc
    return qs.descendant_of(site.root_page, inclusive=True)


def _get_parent_page(parent_pk: int) -> Page:
    try:
        return Page.objects.get(pk=parent_pk)
    except Page.DoesNotExist as exc:
        raise HttpError(400, f"Parent page {parent_pk} not found.") from exc


@router.get(
    "/{page_id}/",
    response={200: PageDetail, 404: Error},
    summary="Get a page (common + contributed fields + body)",
)
def get_page(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
):
    # ETag is computed from the live row (carries the revision
    # timestamp); serialized payload reflects the latest draft so
    # PATCH→GET round-trips return the writer's changes.
    live = resolve_page(page_id)
    response["ETag"] = page_etag(live)
    return serialize_page_detail(resolve_page_for_read(page_id))


@router.patch(
    "/{page_id}/",
    response={
        200: PageDetail,
        400: Error,
        403: Error,
        404: Error,
        412: Error,
        428: Error,
    },
    summary="Patch a page's scalar fields (creates a draft revision)",
)
def patch_page(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    payload: PagePatch,
):
    page = resolve_page(page_id)
    require_edit_permission(request, page)
    require_if_match(request, page)

    data = payload.model_dump(exclude_unset=True)
    with transaction.atomic():
        apply_common_patch(page, data)
        apply_contributed_patch(page, data)
        # save_revision() persists the full in-memory state as a draft and
        # updates latest_revision_created_at on the page row. We do NOT call
        # page.save() — that would write changes directly to the live page
        # row, bypassing the Wagtail revision/publish workflow.
        page.save_revision(user=request.auth)

    # Return the in-memory page (draft state) so the agent sees its changes.
    # The ETag is based on latest_revision_created_at which save_revision()
    # updated, so it is stable and matches a subsequent GET.
    response["ETag"] = page_etag(page)
    return serialize_page_detail(page)


@router.post(
    "/{page_id}/publish/",
    response={
        200: PageDetail,
        403: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Publish the latest draft revision",
)
def publish_page(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
):
    page = resolve_page(page_id)
    require_publish_permission(request, page)
    require_if_match(request, page)

    latest = page.get_latest_revision()
    if latest is None:
        raise HttpError(
            409,
            "Page has no revisions yet — edit it at least once before publishing.",
        )
    latest.publish(user=request.auth)
    fresh = resolve_page(page.pk)
    response["ETag"] = page_etag(fresh)
    return serialize_page_detail(fresh)


@router.post(
    "/{page_id}/unpublish/",
    response={200: PageDetail, 403: Error, 404: Error, 412: Error, 428: Error},
    summary="Take a page offline (post-MVP)",
)
def unpublish_page(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
):
    page = resolve_page(page_id)
    require_publish_permission(request, page)
    require_if_match(request, page)

    page.unpublish(user=request.auth)
    fresh = resolve_page(page.pk)
    response["ETag"] = page_etag(fresh)
    return serialize_page_detail(fresh)
