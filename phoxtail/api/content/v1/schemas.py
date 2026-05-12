"""Pydantic v2 schemas for the content v1 API.

The schemas here cover only what is **generic** to every Wagtail page
— the common fields, the body as opaque JSON, and request/response
envelopes. Per-page-type extra fields are injected into response dicts
at runtime by ``PageSchemaContribution.serialize``; they are not typed
here because the set of page types is extensible.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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


class FocalPoint(Schema):
    x: int
    y: int
    width: int
    height: int


class ImageItem(Schema):
    id: int
    title: str
    width: int
    height: int
    description: str = ""
    tags: list[str] = []
    focal_point: FocalPoint | None = None
    file_url: str | None = None
    collection_id: int | None = None


class ImageList(Schema):
    items: list[ImageItem]
    total: int


class DocumentItem(Schema):
    id: int
    title: str
    description: str = ""
    tags: list[str] = []
    file_size: int | None = None
    filename: str = ""
    file_extension: str = ""
    file_url: str | None = None
    collection_id: int | None = None


class DocumentList(Schema):
    items: list[DocumentItem]
    total: int


class DocumentPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    collection_id: int | None = None


class VideoItem(Schema):
    id: int
    title: str
    description: str = ""
    duration: float = 0.0
    width: int | None = None
    height: int | None = None
    tags: list[str] = []
    file_url: str | None = None
    thumbnail_url: str | None = None
    collection_id: int | None = None


class VideoList(Schema):
    items: list[VideoItem]
    total: int


class VideoPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    collection_id: int | None = None


class AudioItem(Schema):
    id: int
    title: str
    description: str = ""
    duration: float = 0.0
    tags: list[str] = []
    file_url: str | None = None
    collection_id: int | None = None


class AudioList(Schema):
    items: list[AudioItem]
    total: int


class AudioPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    duration: float | None = None
    collection_id: int | None = None


class ImagePatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    focal_point: FocalPoint | None = None
    collection_id: int | None = None


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


class InternalLinkItem(Schema):
    id: int
    uuid: str
    label: str
    url_name: str
    url: str
    created_at: str
    updated_at: str


class InternalLinkList(Schema):
    items: list[InternalLinkItem]
    total: int


class InternalLinkCreate(Schema):
    label: str
    url_name: str


class InternalLinkPatch(Schema):
    label: str | None = None
    url_name: str | None = None


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
