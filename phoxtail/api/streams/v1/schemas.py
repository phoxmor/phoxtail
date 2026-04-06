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
# System prompts
# ---------------------------------------------------------------------------


class PromptSummary(Schema):
    identifier: str
    name: str
    description: str


class Prompt(PromptSummary):
    template: str


class PromptList(Schema):
    prompts: list[PromptSummary]
    total: int


class PromptRenderRequest(Schema):
    """Body for ``POST /prompts/{identifier}/render``.

    ``variant`` is required; ``collection`` defaults to the variant's own
    collection; ``references`` is an optional list of sibling variant
    identifiers (must live in the effective collection). ``block`` is a
    disambiguator for ``variant`` when the identifier is ambiguous across
    blocks.
    """

    variant: str
    block: str | None = None
    collection: str | None = None
    references: list[str] = []


class PromptRenderResponse(Schema):
    prompt: str
    template: PromptSummary
    variant: VariantSummary
    collection: CollectionRef
    references: list[VariantSummary]


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
