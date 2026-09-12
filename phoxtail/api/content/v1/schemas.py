"""Pydantic v2 schemas for the content v1 API.

The schemas here cover only what is **generic** to every Wagtail page
— the common fields, the body as opaque JSON, and request/response
envelopes. Per-page-type extra fields are injected into response dicts
at runtime by ``PageSchemaContribution.serialize``; they are not typed
here because the set of page types is extensible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from ninja import Schema

# ---------------------------------------------------------------------------
# Page list / detail
# ---------------------------------------------------------------------------


class PageSummary(Schema):
    """Slim list-view shape for any Page."""

    id: int
    title: str
    slug: str
    live: bool
    locale: str = ""
    first_published_at: datetime | None = None
    last_published_at: datetime | None = None
    seo_title: str = ""
    search_description: str = ""
    content_type: str
    url: str | None = None


class PageList(Schema):
    pages: list[PageSummary]
    total: int


# PageDetail is intentionally permissive: the common fields plus a free
# ``dict`` of contributed extras. We use ``dict[str, Any]`` as the
# response type rather than enumerating every page subclass in a Union
# — the set of page types is open-ended by design.
PageDetail = dict[str, Any]


# ---------------------------------------------------------------------------
# Page patch
# ---------------------------------------------------------------------------


class PagePatch(Schema):
    """Request body for ``PATCH /pages/{id}/``.

    Accepts any subset of common writable fields at the top level; all
    per-type contributed fields go in the ``fields`` dict and are
    forwarded unchecked to the owning contribution's ``apply_patch``
    (the contribution is responsible for its own validation).

    All common fields are optional; omitted fields are left untouched.
    ``fields`` is a declared dict rather than pydantic extras because
    ninja.Schema's ``from_attributes=True`` default wraps bodies in a
    DjangoGetter that iterates declared fields only, silently dropping
    any top-level ``extra='allow'`` keys.
    """

    title: str | None = None
    slug: str | None = None
    seo_title: str | None = None
    search_description: str | None = None
    fields: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Page create
# ---------------------------------------------------------------------------


class PageCreate(Schema):
    """Request body for ``POST /pages/``.

    ``type`` is the content-type string from the page-types catalog
    (e.g. ``'phoxtail_blog.blogpostpage'``).  ``parent`` is the integer
    PK of the parent page.  ``title`` is the only required Wagtail base
    field; ``slug`` is auto-derived from ``title`` if omitted.

    Per-type contributed fields are passed in ``fields`` as a free dict
    and forwarded to the contribution's ``apply_patch``. See PagePatch
    for why ``fields`` is an explicit dict rather than relying on
    ``extra='allow'``.
    """

    type: str
    parent: int
    title: str
    slug: str | None = None
    seo_title: str = ""
    search_description: str = ""
    fields: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------


BodyValue = list[dict[str, Any]]


class BodyResponse(Schema):
    body: BodyValue


class BodyReplace(Schema):
    """Request body for ``PUT /pages/{id}/body/``."""

    body: BodyValue


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Page-types discovery
# ---------------------------------------------------------------------------


class PageTypeEntry(Schema):
    content_type: str
    writable_fields: dict[str, dict]
    fk_lookups: dict[str, str]


class PageTypeCatalog(Schema):
    types: dict[str, PageTypeEntry]


# ---------------------------------------------------------------------------
# InternalLink
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Page move
# ---------------------------------------------------------------------------

MovePosition = Literal["last-child", "first-child", "left", "right"]


class PageMove(Schema):
    """Request body for ``POST /pages/{id}/move/``.

    ``target`` is the page ID the move is relative to. The meaning
    depends on ``position``:

    * ``"last-child"`` / ``"first-child"`` — target becomes the new
      parent; the page is inserted as its last or first child.
    * ``"left"`` / ``"right"`` — target is a sibling reference; the page
      is inserted immediately before or after it (sharing the same parent).

    ``"last-child"`` is the default and matches the Wagtail admin's
    "Move under" action.
    """

    target: int
    position: MovePosition = "last-child"


# ---------------------------------------------------------------------------
# Copy for translation
# ---------------------------------------------------------------------------


class CopyForTranslationPayload(Schema):
    locale: int
    copy_parents: bool = False
    alias: bool = False
    include_subtree: bool = False


# ---------------------------------------------------------------------------
# Errors — re-exported from streams for consistency
# ---------------------------------------------------------------------------


class Error(Schema):
    detail: str
    title: str | None = None
