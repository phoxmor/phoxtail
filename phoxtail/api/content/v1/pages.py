"""``/api/content/v1/pages/`` — generic Wagtail Page endpoints.

Endpoints:
- ``GET    /``     — list pages (?type, ?parent, ?live, ?search, ?locale, ?site)
- ``POST   /``                    — create a page (draft, not published)
- ``GET    /{page_id}/``          — detail, sets ETag
- ``PATCH  /{page_id}/``          — scalar fields (common + contributed)
- ``DELETE /{page_id}/``          — delete (rejected if has children unless ?force=true)
- ``POST   /{page_id}/publish/``  — publish the latest draft revision
- ``POST   /{page_id}/unpublish/``— take the page offline
- ``POST   /{page_id}/move/``     — move page to a new position in the tree

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

from phoxtail.api.auth import scoped
from phoxtail.api.content.v1._helpers import (
    _check_move_constraints,
    apply_common_patch,
    apply_contributed_patch,
    filter_by_content_type,
    page_etag,
    require_delete_permission,
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
    CopyForTranslationPayload,
    Error,
    PageCreate,
    PageDetail,
    PageList,
    PageMove,
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
    search: str | None = Query(None, description="Autocomplete prefix search on title."),
    locale: str | None = Query(None, description="Filter by locale language code, e.g. 'en'."),
    site: int | None = Query(None, description="Filter by site ID."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    qs = Page.objects.exclude(depth=1).order_by("path")
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


@router.post(
    "/",
    response={201: PageDetail, 400: Error, 403: Error, 404: Error},
    summary="Create a new page as a draft under a given parent",
)
def create_page(
    request: HttpRequest,
    response: HttpResponse,
    payload: PageCreate,
):
    from django.contrib.contenttypes.models import ContentType

    data = payload.model_dump(exclude_unset=True)
    type_string = data.pop("type")
    parent_id = data.pop("parent")
    title = data.pop("title")
    slug = data.pop("slug", None)
    contributed = data.pop("fields", None) or {}

    # Resolve content type → model class.
    try:
        app_label, model_name = type_string.rsplit(".", 1)
    except ValueError as exc:
        raise HttpError(400, f"Invalid page type: '{type_string}'.") from exc
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
    except ContentType.DoesNotExist as exc:
        raise HttpError(400, f"Unknown page type: '{type_string}'.") from exc

    model_cls = ct.model_class()
    if model_cls is None or not issubclass(model_cls, Page):
        raise HttpError(400, f"'{type_string}' is not a Page subclass.")
    if not getattr(model_cls, "is_creatable", True):
        raise HttpError(400, f"'{type_string}' is not directly creatable.")

    # Resolve parent.
    parent = _get_parent_page(parent_id)
    perms = parent.permissions_for_user(request.auth.user)
    if not perms.can_add_subpage():
        raise HttpError(403, "User cannot add pages under that parent.")

    # Build instance. Explicitly draft — add_child() defaults to live=True.
    page = model_cls(title=title, live=False)
    if slug:
        page.slug = slug

    # Enforce parent_page_types / subpage_types before touching the DB.
    if not page.can_create_at(parent):
        raise HttpError(
            400,
            f"'{type_string}' cannot be created under page {parent_id} "
            "(violates parent_page_types or subpage_types constraints).",
        )

    # Apply common optional fields from payload remainder.
    for field in ("seo_title", "search_description"):
        if field in data:
            setattr(page, field, data.pop(field))

    # Apply per-type contributed fields (remaining keys).
    from django.core.exceptions import ValidationError as DjangoValidationError

    from phoxtail.api.content.v1._helpers import apply_contributed_patch

    with transaction.atomic():
        apply_contributed_patch(page, contributed)
        try:
            parent.add_child(instance=page)
            page.save_revision(user=request.auth.user)
        except DjangoValidationError as exc:
            raise HttpError(400, "; ".join(exc.messages)) from exc

    # Re-fetch from DB so serialize_page_detail works against a clean,
    # fully-hydrated instance (avoids 500s from stale in-memory state
    # after add_child mutates the page row).
    fresh = resolve_page(page.pk)
    response["ETag"] = page_etag(fresh)
    return 201, serialize_page_detail(fresh)


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
    contributed = data.pop("fields", None) or {}
    with transaction.atomic():
        apply_common_patch(page, data)
        apply_contributed_patch(page, contributed)
        # save_revision() persists the full in-memory state as a draft and
        # updates latest_revision_created_at on the page row. We do NOT call
        # page.save() — that would write changes directly to the live page
        # row, bypassing the Wagtail revision/publish workflow.
        page.save_revision(user=request.auth.user)

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
    # Wagtail still decides whether this user may publish *this* page, per
    # subtree, and that check is unchanged. This only asks whether the
    # credential they arrived with may be used to publish at all.
    #
    # The codename is read here as the name of an act, not as a claim that
    # the holder has Wagtail's global "Publish any page" permission — a
    # section editor publishes through subtree grants and holds no global
    # one, yet must still be able to scope a token to publishing.
    auth=scoped("wagtailcore.publish_page"),
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
    latest.publish(user=request.auth.user)
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

    page.unpublish(user=request.auth.user)
    fresh = resolve_page(page.pk)
    response["ETag"] = page_etag(fresh)
    return serialize_page_detail(fresh)


@router.post(
    "/{page_id}/copy_for_translation/",
    response={201: PageDetail, 400: Error, 403: Error, 404: Error, 409: Error},
    summary="Copy a page into a new locale (requires simple_translation)",
)
def copy_page_for_translation(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    payload: CopyForTranslationPayload,
):
    from django.db import IntegrityError
    from wagtail.actions.copy_for_translation import (
        CopyPageForTranslationAction,
        CopyPageForTranslationPermissionError,
        ParentNotTranslatedError,
    )
    from wagtail.models import Locale

    page = resolve_page(page_id)

    try:
        locale = Locale.objects.get(pk=payload.locale)
    except Locale.DoesNotExist as exc:
        raise HttpError(404, f"Locale {payload.locale} not found.") from exc

    if page.has_translation(locale):
        raise HttpError(
            409,
            f"Page already has a translation in locale '{locale.language_code}'. "
            "Use phoxtail_pages_list_pages with locale= to find it.",
        )

    action = CopyPageForTranslationAction(
        page=page,
        locale=locale,
        copy_parents=payload.copy_parents,
        alias=payload.alias,
        include_subtree=payload.include_subtree,
        user=request.auth.user,
    )
    try:
        with transaction.atomic():
            translated_page = action.execute()
    except CopyPageForTranslationPermissionError as exc:
        raise HttpError(403, str(exc)) from exc
    except ParentNotTranslatedError:
        raise HttpError(
            400,
            "Parent page is not translated into the target locale. "
            "Pass copy_parents=true to automatically copy untranslated parent pages.",
        )
    except IntegrityError:
        raise HttpError(
            409,
            f"One or more pages in the subtree already have a translation in "
            f"locale '{locale.language_code}'. The entire operation was rolled back.",
        )

    fresh = resolve_page(translated_page.pk)
    response["ETag"] = page_etag(fresh)
    return 201, serialize_page_detail(fresh)


@router.post(
    "/{page_id}/move/",
    response={200: PageDetail, 400: Error, 403: Error, 404: Error, 412: Error, 428: Error},
    summary="Move a page to a new position in the tree",
)
def move_page(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    payload: PageMove,
):
    from treebeard.exceptions import InvalidMoveToDescendant
    from wagtail.actions.move_page import MovePageAction, MovePagePermissionError

    page = resolve_page(page_id)
    require_if_match(request, page)

    if payload.target == page_id:
        raise HttpError(400, "A page cannot be moved relative to itself.")

    try:
        target = Page.objects.get(pk=payload.target)
    except Page.DoesNotExist as exc:
        raise HttpError(404, f"Target page {payload.target} not found.") from exc

    if target.is_root():
        raise HttpError(400, "Cannot move a page onto the Wagtail root node.")

    # Determine parent_after so we can validate type constraints before
    # handing off to MovePageAction (which conflates type violations and
    # permission errors into a single MovePagePermissionError/403).
    child_positions = {"first-child", "last-child", "sorted-child"}
    parent_after = target if payload.position in child_positions else target.get_parent()

    _check_move_constraints(page.specific, parent_after)

    action = MovePageAction(page=page.specific, target=target, pos=payload.position, user=request.auth.user)
    try:
        with transaction.atomic():
            action.execute()
    except MovePagePermissionError as exc:
        raise HttpError(403, str(exc)) from exc
    except InvalidMoveToDescendant:
        raise HttpError(400, "Cannot move a page under itself or one of its descendants.")

    # Re-fetch from the live row — MovePageAction rewrites url_path on the
    # live row but does not create a revision, so resolve_page_for_read
    # would return a stale pre-move URL from the revision snapshot.
    fresh = resolve_page(page_id)
    response["ETag"] = page_etag(fresh)
    return serialize_page_detail(fresh)


@router.delete(
    "/{page_id}/",
    response={204: None, 400: Error, 403: Error, 404: Error, 412: Error, 428: Error},
    summary="Delete a page (and its children if force=true)",
)
def delete_page(
    request: HttpRequest,
    page_id: int,
    force: bool = False,
):
    page = resolve_page(page_id)
    require_delete_permission(request, page)
    require_if_match(request, page)

    child_count = page.get_children().count()
    if child_count > 0 and not force:
        raise HttpError(
            400,
            f"Page {page_id} has {child_count} child page(s). "
            "Pass force=true to delete the page and all its descendants.",
        )

    with transaction.atomic():
        page.delete()

    return 204, None
