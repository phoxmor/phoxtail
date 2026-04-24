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

    Accepts any subset of common + contributed writable fields. The core
    endpoint validates common fields via this schema and forwards the
    raw dict (``__pydantic_extra__``) to the contribution's
    ``apply_patch``, so contributed fields pass through unchecked at
    the schema level — the contribution is responsible for its own
    validation.

    All common fields are optional; omitted fields are left untouched.
    """

    model_config = {"extra": "allow"}

    title: str | None = None
    slug: str | None = None
    seo_title: str | None = None
    search_description: str | None = None


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
    description: str = ""
    tags: list[str] = []
    focal_point: FocalPoint | None = None
    file_url: str | None = None


class ImageList(Schema):
    items: list[ImageItem]
    total: int


class DocumentItem(Schema):
    id: int
    title: str
    description: str = ""
    file_url: str | None = None


class DocumentList(Schema):
    items: list[DocumentItem]
    total: int


class ImagePatch(Schema):
    description: str | None = None
    tags: list[str] | None = None
    focal_point: FocalPoint | None = None


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
# Errors — re-exported from streams for consistency
# ---------------------------------------------------------------------------


class Error(Schema):
    detail: str
    title: str | None = None
