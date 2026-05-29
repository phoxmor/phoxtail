"""Pydantic v2 schemas for the streams v1 API.

These schemas are the stable contract for every consumer of the API —
the ``phoxtail`` CLI, the MCP server, and (from Phase 5 onwards) remote
Phoxtail projects acting as sync peers. Field names and shapes here are
breaking-change territory: any change forces a v2.
"""

from __future__ import annotations

from ninja import Field, Schema

# ---------------------------------------------------------------------------
# Shared references
# ---------------------------------------------------------------------------


class BlockRef(Schema):
    """Minimal embed of a block, used inside variant responses."""

    id: int
    identifier: str
    name: str


class CollectionRef(Schema):
    """Minimal embed of a collection, used inside variant responses."""

    id: int
    identifier: str
    name: str


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


class VariantSummary(Schema):
    """List-view shape for a BlockVariant."""

    id: int
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
    block_id: int
    collection_id: int
    description: str = ""
    html: str = ""
    css: str = ""
    javascript: str = ""
    is_default: bool = False


class VariantUpdate(Schema):
    """Request body for ``PUT /variants/{variant_id}``.

    All fields are optional; omitted fields are left untouched. The ETag
    check happens via the ``If-Match`` header, not in the body.
    """

    identifier: str | None = None
    name: str | None = None
    description: str | None = None
    collection_id: int | None = None
    preview_image_id: int | None = None
    html: str | None = None
    css: str | None = None
    javascript: str | None = None
    is_default: bool | None = None


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class CollectionSummary(Schema):
    id: int
    identifier: str
    name: str
    description: str
    variant_count: int


class Collection(CollectionSummary):
    template: str


class CollectionList(Schema):
    collections: list[CollectionSummary]
    total: int


class CollectionCreate(Schema):
    """Request body for ``POST /collections/``."""

    identifier: str
    name: str
    description: str = ""
    template: str = ""


class CollectionUpdate(Schema):
    """Request body for ``PATCH /collections/{collection_id}/``.

    All fields are optional; omitted fields are left untouched. The ETag
    check happens via the ``If-Match`` header, not in the body.
    """

    identifier: str | None = None
    name: str | None = None
    description: str | None = None
    template: str | None = None


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


class BlockSummary(Schema):
    id: int
    identifier: str
    name: str
    description: str
    group: str
    icon: str
    is_shared: bool
    variant_count: int


class BlockVariantRef(Schema):
    """Minimal variant embed used inside block detail responses."""

    id: int
    identifier: str
    name: str
    is_default: bool
    collection: CollectionRef


class Block(BlockSummary):
    page_types: list[str]
    variants: list[BlockVariantRef]
    field_schema: str = ""
    sort_order: int = 0


class BlockList(Schema):
    blocks: list[BlockSummary]
    total: int


class BlockCreate(Schema):
    """Request body for ``POST /blocks/``."""

    identifier: str
    name: str
    description: str = ""
    icon: str = ""
    group: str = ""
    is_shared: bool = False
    page_types: list[str] = []
    block_schema: list[dict] = Field([], alias="schema")
    sort_order: int = 0


class BlockUpdate(Schema):
    """Request body for ``PATCH /blocks/{block_id}/``.

    All fields are optional; omitted fields are left untouched. The ETag
    check happens via the ``If-Match`` header, not in the body.
    """

    identifier: str | None = None
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    group: str | None = None
    is_shared: bool | None = None
    page_types: list[str] | None = None
    block_schema: list[dict] | None = Field(None, alias="schema")
    sort_order: int | None = None


# ---------------------------------------------------------------------------
# Block Categories
# ---------------------------------------------------------------------------


class BlockCategoryItem(Schema):
    id: int
    name: str
    slug: str
    description: str


class BlockCategoryList(Schema):
    items: list[BlockCategoryItem]
    total: int


class BlockCategoryCreate(Schema):
    name: str
    slug: str
    description: str = ""


class BlockCategoryUpdate(Schema):
    name: str | None = None
    slug: str | None = None
    description: str | None = None


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
    """Collection data for the context document, including design guidelines."""

    identifier: str
    name: str
    description: str
    design_guidelines: str


class DesignTokenRole(Schema):
    """A single palette or font role."""

    name: str
    identifier: str
    description: str


class DesignTokens(Schema):
    """Site-wide design tokens included in the context response."""

    palette_roles: list[DesignTokenRole]
    font_roles: list[DesignTokenRole]


class ContextReferenceVariant(Schema):
    """Reference variant with full content and parent block reference."""

    identifier: str
    name: str
    description: str
    html: str
    css: str
    javascript: str
    block: BlockRef


class ContextRequest(Schema):
    """Body for ``POST /context/``.

    ``block_id`` and ``collection_id`` are required. ``references`` is an
    optional list of variant IDs to include as inspiration.
    """

    block_id: int
    collection_id: int
    references: list[int] = []


class ContextResponse(Schema):
    """Structured data for rendering the context template."""

    block: ContextBlockRef
    collection: ContextCollectionRef
    design_tokens: DesignTokens
    references: list[ContextReferenceVariant]


# ---------------------------------------------------------------------------
# Shared Blocks
# ---------------------------------------------------------------------------


class SharedBlockSummary(Schema):
    id: int
    block_id: int
    block: BlockRef
    site_id: int
    site_hostname: str
    locale_id: int
    language_code: str
    created_at: str
    updated_at: str


class SharedBlock(SharedBlockSummary):
    content: str


class SharedBlockList(Schema):
    shared_blocks: list[SharedBlockSummary]
    total: int


class SharedBlockCreate(Schema):
    """Request body for ``POST /shared-blocks/``."""

    block_id: int
    site_id: int
    locale_id: int
    content: list[dict] = []


class SharedBlockUpdate(Schema):
    """Request body for ``PATCH /shared-blocks/{id}/``.

    Only ``content`` may be changed after creation. The block/site/locale
    triplet is immutable. The ETag check happens via ``If-Match``.
    """

    content: list[dict] | None = None


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
