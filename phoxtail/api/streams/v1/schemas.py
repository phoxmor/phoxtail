"""Pydantic v2 schemas for the streams v1 API.

These schemas are the stable contract for every consumer of the API —
the ``phoxtail`` CLI, the MCP server, and (from Phase 5 onwards) remote
Phoxtail projects acting as sync peers. Field names and shapes here are
breaking-change territory: any change forces a v2.
"""

from __future__ import annotations

from ninja import Schema

# ---------------------------------------------------------------------------
# Shared references
# ---------------------------------------------------------------------------


class BlockRef(Schema):
    """Minimal embed of a block, used inside variant responses."""

    identifier: str
    name: str


class CollectionRef(Schema):
    """Minimal embed of a collection, used inside variant responses."""

    identifier: str
    name: str


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


class VariantSummary(Schema):
    """List-view shape for a BlockVariant."""

    identifier: str
    name: str
    description: str
    is_default: bool
    block: BlockRef
    collection: CollectionRef


class Variant(VariantSummary):
    """Detail-view shape for a BlockVariant. Adds the three content fields."""

    html: str
    css: str
    javascript: str


class VariantList(Schema):
    variants: list[VariantSummary]
    total: int


class VariantCreate(Schema):
    """Request body for ``POST /variants/``."""

    identifier: str
    name: str
    block: str
    collection: str
    description: str = ""
    html: str = ""
    css: str = ""
    javascript: str = ""


class VariantUpdate(Schema):
    """Request body for ``PUT /variants/{identifier}``.

    All fields are optional; omitted fields are left untouched. The ETag
    check happens via the ``If-Match`` header, not in the body.
    """

    html: str | None = None
    css: str | None = None
    javascript: str | None = None


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class CollectionSummary(Schema):
    identifier: str
    name: str
    description: str
    variant_count: int


class Collection(CollectionSummary):
    template: str


class CollectionRendered(Schema):
    """Response for ``POST /collections/{identifier}/render``."""

    identifier: str
    name: str
    description: str
    design_tokens: str


class CollectionList(Schema):
    collections: list[CollectionSummary]
    total: int


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


class BlockSummary(Schema):
    identifier: str
    name: str
    description: str
    group: str
    icon: str
    is_shared: bool
    variant_count: int


class BlockVariantRef(Schema):
    """Minimal variant embed used inside block detail responses."""

    identifier: str
    name: str
    is_default: bool
    collection: CollectionRef


class Block(BlockSummary):
    page_types: list[str]
    variants: list[BlockVariantRef]


class BlockList(Schema):
    blocks: list[BlockSummary]
    total: int


# ---------------------------------------------------------------------------
# Context (agent briefing)
# ---------------------------------------------------------------------------


class ContextBlockRef(Schema):
    """Block data for the context document, including the full schema."""

    identifier: str
    name: str
    description: str
    field_schema: str


class ContextCollectionRef(Schema):
    """Collection data for the context document, including rendered tokens."""

    identifier: str
    name: str
    description: str
    design_tokens: str


class ContextVariant(Schema):
    """Variant data for the context document — full content included."""

    identifier: str
    name: str
    description: str
    html: str
    css: str
    javascript: str


class ContextReferenceVariant(ContextVariant):
    """Reference variant with its parent block reference."""

    block: BlockRef


class ContextRequest(Schema):
    """Body for ``POST /context/``.

    Both ``block`` and ``variant`` are required. The variant's own
    collection is always used for design tokens. ``references`` is an
    optional list of variant identifiers from the same collection.
    """

    block: str
    variant: str
    references: list[str] = []


class ContextResponse(Schema):
    """Structured data for rendering the context template."""

    block: ContextBlockRef
    variant: ContextVariant
    collection: ContextCollectionRef
    references: list[ContextReferenceVariant]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class Error(Schema):
    """Uniform error envelope returned on 4xx responses.

    Shape intentionally mirrors RFC 7807 Problem Details at the field
    level (``detail``, ``title``) so we can harden it into a true
    ``application/problem+json`` response later without changing clients.
    """

    detail: str
    title: str | None = None
