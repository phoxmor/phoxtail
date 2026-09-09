"""Shared helpers for the pages v1 routers.

ETags, permission checks, and common-field serialization live here so
that the resource routers (``pages.py``, ``body.py``) stay focused on
request plumbing.
"""

from __future__ import annotations

import hashlib
from typing import Any

from django.core.exceptions import ValidationError
from django.http import HttpRequest
from ninja.errors import HttpError
from wagtail.models import Page

from phoxtail.api.content.v1.contrib import (
    PageSchemaContribution,
    get_contribution_for_page,
)

# ---------------------------------------------------------------------------
# ETags — page-level, covers scalar + body + latest_revision_created_at
# ---------------------------------------------------------------------------


def page_etag(page: Page) -> str:
    """Compute a weak ETag for the whole page.

    Uses pk + latest_revision_created_at + last_published_at + live.
    ``latest_revision_created_at`` is updated by ``save_revision()`` and
    is the authoritative change signal for draft state; scalar fields
    are intentionally not hashed, since their draft values may diverge
    from the live row and the revision timestamp already covers any
    change to them.
    """
    h = hashlib.sha256()
    h.update(str(page.pk).encode("utf-8"))
    h.update(b"\x00")
    h.update(str(page.latest_revision_created_at or "").encode("utf-8"))
    h.update(b"\x00")
    h.update(str(page.last_published_at or "").encode("utf-8"))
    h.update(b"\x00")
    h.update(b"1" if page.live else b"0")
    return f'W/"{h.hexdigest()[:16]}"'


def etag_matches(header_value: str | None, current: str) -> bool:
    """Tolerant ``If-Match`` comparison (RFC 7232 — weak validators)."""
    if not header_value:
        return False
    candidates = {tag.strip() for tag in header_value.split(",")}
    normalized = {_strip_weak_prefix(t) for t in candidates}
    return _strip_weak_prefix(current) in normalized or "*" in candidates


def _strip_weak_prefix(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


def require_if_match(request: HttpRequest, page: Page) -> None:
    """Raise 428 if ``If-Match`` missing, 412 if it doesn't match."""
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this page.",
        )
    current = page_etag(page)
    if not etag_matches(if_match, current):
        raise HttpError(
            412,
            "ETag mismatch: the page has changed since you last read it. Re-fetch and retry.",
        )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve_page(page_id: int) -> Page:
    """Fetch a Page by primary key, downcast to its specific subclass.

    Returns the **live** row — the persisted DB state, not any pending
    draft. Use this for writes (``save_revision``, ``publish``) and for
    permission checks; use :func:`resolve_page_for_read` to surface
    draft state to a reader.

    The Wagtail root page (depth=1) is invisible to this API — it is an
    internal structural node, not a content page. Requests for it 404.
    """
    try:
        page = Page.objects.get(pk=page_id)
    except Page.DoesNotExist as exc:
        raise HttpError(404, f"Page {page_id} not found.") from exc
    if page.is_root():
        raise HttpError(404, f"Page {page_id} not found.")
    return page.specific


def resolve_page_for_read(page_id: int) -> Page:
    """Fetch a Page for GET, surfacing any pending draft revision.

    Wagtail's ``save_revision()`` writes the revision JSON to a
    ``Revision`` row *without* updating the canonical ``wagtailcore_page``
    row. A naive ``Page.objects.get(pk=...)`` would therefore return
    stale scalars after a PATCH. We use
    ``get_latest_revision_as_object()`` so that:

    * for a page with pending edits, the draft state is returned;
    * for a page with no revisions (freshly bootstrapped), the live
      row is returned unchanged (Wagtail falls back to ``self.specific``
      internally).

    Writes still resolve via :func:`resolve_page` so that
    ``save_revision`` and ``publish`` operate on the persisted instance.
    """
    live = resolve_page(page_id)
    latest = live.get_latest_revision()
    if latest is None:
        return live
    return latest.as_object()


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def require_publish_permission(request: HttpRequest, page: Page) -> None:
    """Raise 403 if ``request.auth.user`` cannot publish the page."""
    user = request.auth.user
    perms = page.permissions_for_user(user)
    if not perms.can_publish():
        raise HttpError(403, "User cannot publish this page.")


def require_edit_permission(request: HttpRequest, page: Page) -> None:
    """Raise 403 if ``request.auth.user`` cannot edit the page."""
    user = request.auth.user
    perms = page.permissions_for_user(user)
    if not perms.can_edit():
        raise HttpError(403, "User cannot edit this page.")


def require_delete_permission(request: HttpRequest, page: Page) -> None:
    """Raise 403 if ``request.auth.user`` cannot delete the page."""
    user = request.auth.user
    perms = page.permissions_for_user(user)
    if not perms.can_delete():
        raise HttpError(403, "User cannot delete this page.")


# ---------------------------------------------------------------------------
# Serialization — common page fields + contributed extras
# ---------------------------------------------------------------------------


def content_type_string(page: Page) -> str:
    cls = page.specific_class or type(page)
    return f"{cls._meta.app_label}.{cls._meta.model_name}"


def common_fields(page: Page) -> dict[str, Any]:
    """Core Wagtail fields exposed on every page."""
    locale_code = ""
    if hasattr(page, "locale_id") and page.locale_id is not None:
        locale_code = getattr(page.locale, "language_code", "")
    return {
        "id": page.pk,
        "title": page.title,
        "slug": page.slug,
        "live": page.live,
        "locale": locale_code,
        "first_published_at": page.first_published_at,
        "last_published_at": page.last_published_at,
        "seo_title": page.seo_title,
        "search_description": page.search_description,
        "content_type": content_type_string(page),
        "url": _safe_full_url(page),
    }


def _safe_full_url(page: Page) -> str | None:
    """Return the page's full URL, or None if it has never been published.

    Narrows exception handling to the known failure modes: an
    uninitialised Wagtail Site config (``Site.DoesNotExist``) and
    URL-resolution failures (``NoReverseMatch``). Anything else is a
    real bug and should surface.
    """
    if not page.live and not page.first_published_at:
        return None
    from django.urls import NoReverseMatch
    from wagtail.models import Site

    try:
        return page.get_full_url()
    except (Site.DoesNotExist, NoReverseMatch):
        return None


def serialize_page_detail(page: Page) -> dict[str, Any]:
    """Full GET /pages/{id}/ body: common fields + contributed extras.

    ``parent`` is here rather than in :func:`common_fields` on purpose:
    resolving it costs a query per page, which a list view would pay
    once per row. A detail response is a single page, and where it sits
    is what lets a caller reason about the tree around it.
    """
    base = common_fields(page)
    parent = page.get_parent()
    base["parent"] = parent.pk if parent is not None else None
    contribution = get_contribution_for_page(page)
    if contribution is not None:
        extra = contribution.serialize(page)
        base.update(extra)
    return base


def serialize_page_summary(page: Page) -> dict[str, Any]:
    """Slim list-view shape — no body, no contributed extras."""
    return common_fields(page)


# ---------------------------------------------------------------------------
# Patching
# ---------------------------------------------------------------------------


COMMON_WRITABLE_FIELDS = {"title", "slug", "seo_title", "search_description"}


def apply_common_patch(page: Page, data: dict[str, Any]) -> None:
    """Apply writable common fields to the page instance (no save)."""
    for key in COMMON_WRITABLE_FIELDS:
        if key in data and data[key] is not None:
            setattr(page, key, data[key])


def apply_contributed_patch(page: Page, data: dict[str, Any]) -> None:
    contribution = get_contribution_for_page(page)
    if contribution is not None:
        contribution.apply_patch(page, data)


# ---------------------------------------------------------------------------
# Body (StreamField) serialization helpers
# ---------------------------------------------------------------------------


def serialize_body(page: Page, field_name: str = "body") -> list[dict[str, Any]]:
    """Return the page's StreamField body as a JSON-ready list of dicts.

    **Public contribution API** — any ``PageSchemaContribution.serialize``
    callable should call this rather than reimplementing the
    ``stream_block.get_api_representation(...)`` dance. Keeping a single
    implementation means future changes (context-aware serialization,
    alternate body field names, etc.) land in one place.

    Uses Wagtail's ``get_api_representation``, the documented
    round-trippable JSON shape consumed by
    ``PUT /pages/{id}/body/``.
    """
    stream_value = getattr(page, field_name, None)
    if stream_value is None:
        return []
    stream_block = stream_value.stream_block
    return stream_block.get_api_representation(stream_value, context=None) or []


def replace_body(
    page: Page,
    new_value: list[dict[str, Any]],
    field_name: str = "body",
) -> None:
    """Replace the page's StreamField body with the given list.

    Accepts the round-trippable ``[{type, value, id}, ...]`` format. The
    value is set on the page but not saved — the caller saves a revision.

    ``StreamBlock.to_python`` is lazy: it wraps the raw dicts without
    validating anything below the top level, so a malformed nested block
    (e.g. a StreamBlock field inside a StructBlock given ``[null, null]``
    instead of ``[{type, value, id}, ...]``) sails through untouched and
    only blows up later — during rendering or in the admin editor, by
    which point it may already be committed to a revision. Forcing a full
    ``get_api_representation`` pass here, before the caller's
    ``save_revision()``, makes this the single place that catches that
    corruption for every block-write endpoint (add/update/delete/move/
    replace all funnel through this function).
    """
    stream_value = getattr(page, field_name, None)
    if stream_value is None:
        raise HttpError(400, f"Page has no StreamField named '{field_name}'.")
    stream_block = stream_value.stream_block
    try:
        # ``to_python`` converts the JSON-ready form back into a StreamValue.
        # It already raises TypeError/KeyError on a malformed *top-level*
        # entry (e.g. a bare `null`, or a dict missing "type"); wrapping it
        # together with get_api_representation below means both the
        # top-level and nested-block failure paths land on the same 400.
        python_value = stream_block.to_python(new_value)
        stream_block.get_api_representation(python_value, context=None)
    except (TypeError, KeyError, AttributeError, ValueError, ValidationError) as exc:
        raise HttpError(
            400,
            "Invalid body: could not materialize the new value "
            f"({exc}). Every stream/list block entry — including "
            "nested ones inside struct fields — must be a "
            "{'type': ..., 'value': ..., 'id': ...} dict; None or "
            "other placeholder values are not valid block entries.",
        ) from exc
    setattr(page, field_name, python_value)


def body_field_name_for(page: Page) -> str:
    """Return the name of the StreamField used as 'body' on this page.

    For now all Phoxtail pages use ``body``; contributions can override
    via a custom ``serialize`` that picks a different field, but the
    default is fine.
    """
    return "body"


# ---------------------------------------------------------------------------
# Convenience — dump contribution metadata
# ---------------------------------------------------------------------------


def contribution_as_dict(contrib: PageSchemaContribution) -> dict[str, Any]:
    """Serialize a PageSchemaContribution for the /page-types/ endpoint."""
    model = contrib.model
    return {
        "content_type": contrib.content_type,
        "is_creatable": getattr(model, "is_creatable", True),
        "parent_page_types": list(getattr(model, "parent_page_types", []) or []),
        "subpage_types": list(getattr(model, "subpage_types", []) or []),
        "writable_fields": contrib.writable_fields,
        "fk_lookups": dict(contrib.fk_lookups),
    }


# ---------------------------------------------------------------------------
# Move validation — decomposes can_move_to() into distinct 400 reasons
# ---------------------------------------------------------------------------


def _check_move_constraints(specific_page, parent_after) -> None:
    """Raise HttpError(400) with an accurate reason if the move is forbidden.

    Mirrors the three rejection branches inside Page.can_move_to() so each
    failure produces a distinct, actionable message rather than the generic
    "cannot be placed under" line that can_move_to()'s boolean return hides.
    """
    from ninja.errors import HttpError

    # 1. Locale-section mismatch (non-root parents must share the locale).
    parent_is_root = parent_after.depth == 1
    if not parent_is_root and getattr(parent_after, "locale_id", None) != getattr(specific_page, "locale_id", None):
        page_locale = getattr(getattr(specific_page, "locale", None), "language_code", "?")
        parent_locale = getattr(getattr(parent_after, "locale", None), "language_code", "?")
        raise HttpError(
            400,
            f"Cannot move across language sections: page is '{page_locale}', target parent is '{parent_locale}'.",
        )

    # 2. parent_page_types / subpage_types violation.
    if not specific_page.can_exist_under(parent_after):
        page_type = f"{specific_page._meta.app_label}.{specific_page.__class__.__name__}"
        parent_type = f"{parent_after.specific_class._meta.app_label}.{parent_after.specific_class.__name__}"
        allowed = [f"{m._meta.app_label}.{m.__name__}" for m in specific_page.__class__.allowed_parent_page_models()]
        hint = f" Allowed parent types: {', '.join(allowed)}." if allowed else ""
        raise HttpError(400, f"'{page_type}' cannot be placed under '{parent_type}'.{hint}")

    # 3. max_count_per_parent exceeded at the destination.
    max_cpp = getattr(specific_page, "max_count_per_parent", None)
    if max_cpp is not None:
        existing = parent_after.get_children().type(specific_page.__class__).not_page(specific_page).count()
        if existing >= max_cpp:
            page_type = f"{specific_page._meta.app_label}.{specific_page.__class__.__name__}"
            raise HttpError(
                400,
                f"Target already contains the maximum number of '{page_type}' pages ({max_cpp} allowed).",
            )


# ---------------------------------------------------------------------------
# Small utility: parse ?type=phoxtail_blog.BlogPostPage filter
# ---------------------------------------------------------------------------


def filter_by_content_type(queryset, type_string: str):
    """Filter a Page queryset by an ``app_label.ModelName`` string.

    400 is returned for a malformed string; 404 is returned for a
    well-formed string that references an app/model not installed in
    the current project (e.g. ``phoxtail_blog.BlogPostPage`` in a
    project without blog). This lets the agent distinguish "I typed it
    wrong" from "that type isn't available here".
    """
    from django.contrib.contenttypes.models import ContentType

    try:
        app_label, model_name = type_string.rsplit(".", 1)
    except ValueError as exc:
        raise HttpError(400, f"Invalid page type filter: '{type_string}'.") from exc
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
    except ContentType.DoesNotExist as exc:
        raise HttpError(404, f"Unknown page type: '{type_string}'.") from exc
    return queryset.filter(content_type=ct)
