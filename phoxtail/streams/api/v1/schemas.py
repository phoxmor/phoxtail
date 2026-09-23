"""Pydantic v2 schemas for the streams v1 API.

These schemas are the contract for every consumer of the API — the
``phoxtail`` CLI, the MCP server, and remote Phoxtail projects acting as
sync peers. Until phoxtail reaches 1.0 a breaking change stays in v1 and is
announced in the changelog; from 1.0 on, one forces a v2.

Responses are shaped here, from the model instances the endpoints return:
a field the model does not hold as-is has a ``resolve_<field>`` beside it.
"""

from __future__ import annotations

import json
from datetime import datetime

from ninja import Field, Schema

from phoxtail.api.schemas import NonBlank
from phoxtail.streams.api.v1._helpers import variant_content_hash
from phoxtail.streams.utils import _image_url


def _page_types(block) -> list[str]:
    return [f"{ct.app_label}.{ct.model}" for ct in block.page_types.all()]


def _counted(obj, relation: str) -> int:
    # Lists annotate the count onto their query; one row counts itself.
    if "variant_count" in obj.__dict__:
        return obj.variant_count
    return getattr(obj, relation).count()


# ---------------------------------------------------------------------------
# Shared references
# ---------------------------------------------------------------------------


class BlockRef(Schema):
    """Minimal embed of a block, used inside variant responses."""

    id: int
    identifier: str
    name: str
    source_app: str = ""
    page_types: list[str] = []

    @staticmethod
    def resolve_page_types(block) -> list[str]:
        return _page_types(block)


class VariantCollectionRef(Schema):
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
    collection: VariantCollectionRef | None = None
    preview_desktop_light_url: str = ""
    preview_desktop_dark_url: str = ""
    preview_tablet_light_url: str = ""
    preview_tablet_dark_url: str = ""
    preview_mobile_light_url: str = ""
    preview_mobile_dark_url: str = ""
    content_hash: str = ""

    @staticmethod
    def resolve_content_hash(variant) -> str:
        return variant_content_hash(variant)

    @staticmethod
    def resolve_preview_desktop_light_url(variant) -> str:
        return _image_url(variant.preview_image_desktop) or ""

    @staticmethod
    def resolve_preview_desktop_dark_url(variant) -> str:
        return _image_url(variant.preview_image_desktop_dark) or ""

    @staticmethod
    def resolve_preview_tablet_light_url(variant) -> str:
        return _image_url(variant.preview_image_tablet) or ""

    @staticmethod
    def resolve_preview_tablet_dark_url(variant) -> str:
        return _image_url(variant.preview_image_tablet_dark) or ""

    @staticmethod
    def resolve_preview_mobile_light_url(variant) -> str:
        return _image_url(variant.preview_image_mobile) or ""

    @staticmethod
    def resolve_preview_mobile_dark_url(variant) -> str:
        return _image_url(variant.preview_image_mobile_dark) or ""


class Variant(VariantSummary):
    """Detail-view shape for a BlockVariant. Adds the three content fields."""

    html: str
    css: str
    javascript: str


class VariantCreate(Schema):
    """Request body for ``POST /variants/``."""

    identifier: str
    name: str
    block_id: int
    collection_id: int | None = None
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
    preview_image_desktop_id: int | None = None
    preview_image_desktop_dark_id: int | None = None
    preview_image_tablet_id: int | None = None
    preview_image_tablet_dark_id: int | None = None
    preview_image_mobile_id: int | None = None
    preview_image_mobile_dark_id: int | None = None
    html: str | None = None
    css: str | None = None
    javascript: str | None = None
    is_default: bool | None = None


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class VariantCollectionSummary(Schema):
    id: int
    identifier: str
    name: str
    description: str
    variant_count: int

    @staticmethod
    def resolve_variant_count(collection) -> int:
        return _counted(collection, "variants")


class VariantCollectionCreate(Schema):
    """Request body for ``POST /collections/``."""

    identifier: NonBlank
    name: NonBlank
    description: NonBlank


class VariantCollectionUpdate(Schema):
    """Request body for ``PATCH /collections/{collection_id}/``.

    All fields are optional; omitted fields are left untouched. The ETag
    check happens via the ``If-Match`` header, not in the body.
    """

    identifier: NonBlank | None = None
    name: NonBlank | None = None
    description: NonBlank | None = None


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
    site_slot: str = ""
    slot_order: int = 0
    render_in_preview: bool = True
    source_app: str
    variant_count: int

    @staticmethod
    def resolve_variant_count(block) -> int:
        return _counted(block, "variants")


class BlockVariantRef(Schema):
    """Minimal variant embed used inside block detail responses."""

    id: int
    identifier: str
    name: str
    is_default: bool
    collection: VariantCollectionRef | None = None


class Block(BlockSummary):
    page_types: list[str]
    variants: list[BlockVariantRef]
    field_schema: str = ""
    sort_order: int = 0

    @staticmethod
    def resolve_page_types(block) -> list[str]:
        return _page_types(block)

    @staticmethod
    def resolve_variants(block) -> list:
        return list(block.variants.select_related("collection"))

    @staticmethod
    def resolve_field_schema(block) -> str:
        return json.dumps(block.schema.get_prep_value(), indent=2)

    @staticmethod
    def resolve_sort_order(block) -> int:
        return block.sort_order or 0


class BlockCreate(Schema):
    """Request body for ``POST /blocks/``."""

    identifier: NonBlank
    name: NonBlank
    description: NonBlank
    icon: str = ""
    group: str = ""
    is_shared: bool = False
    site_slot: str = ""
    slot_order: int = 0
    render_in_preview: bool = True
    page_types: list[str] = []
    block_schema: list[dict] = Field([], alias="schema")
    sort_order: int = 0


class BlockUpdate(Schema):
    """Request body for ``PATCH /blocks/{block_id}/``.

    All fields are optional; omitted fields are left untouched. The ETag
    check happens via the ``If-Match`` header, not in the body.
    """

    identifier: NonBlank | None = None
    name: NonBlank | None = None
    description: NonBlank | None = None
    icon: str | None = None
    group: str | None = None
    is_shared: bool | None = None
    site_slot: str | None = None
    slot_order: int | None = None
    render_in_preview: bool | None = None
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


class BlockCategoryCreate(Schema):
    name: NonBlank
    slug: NonBlank
    description: str = ""


class BlockCategoryUpdate(Schema):
    name: NonBlank | None = None
    slug: NonBlank | None = None
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

    @staticmethod
    def resolve_field_schema(block) -> str:
        return json.dumps(block.schema.get_prep_value(), indent=2)


class ContextCollectionRef(Schema):
    """Optional collection label embedded in the context document."""

    identifier: str
    name: str
    description: str


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
    collection_id: int | None = None
    references: list[int] = []


class ContextResponse(Schema):
    """Structured data for rendering the context template."""

    block: ContextBlockRef
    collection: ContextCollectionRef | None = None
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
    variant_id: int | None = None
    variant_identifier: str = ""
    created_at: datetime | None = None
    updated_at: datetime

    @staticmethod
    def resolve_site_hostname(shared_block) -> str:
        return shared_block.site.hostname

    @staticmethod
    def resolve_language_code(shared_block) -> str:
        return shared_block.locale.language_code

    @staticmethod
    def resolve_variant_identifier(shared_block) -> str:
        return shared_block.variant.identifier if shared_block.variant_id else ""


class SharedBlock(SharedBlockSummary):
    content: str

    @staticmethod
    def resolve_content(shared_block) -> str:
        return json.dumps(shared_block.content.get_prep_value() or [], indent=2)


class SharedBlockCreate(Schema):
    """Request body for ``POST /shared-blocks/``."""

    block_id: int
    site_id: int
    locale_id: int
    variant_id: int | None = None
    content: list[dict] = []


class SharedBlockUpdate(Schema):
    """Request body for ``PATCH /shared-blocks/{id}/``.

    ``content`` and ``variant_id`` may be changed after creation; the
    block/site/locale triplet is immutable. Passing ``variant_id: null``
    explicitly clears the variant (omitting it leaves it untouched). The
    ETag check happens via ``If-Match``.
    """

    content: list[dict] | None = None
    variant_id: int | None = None


# ---------------------------------------------------------------------------
# Push (cross-project sync — receiving side)
# ---------------------------------------------------------------------------


class PushCollectionData(Schema):
    name: str
    identifier: str


class PushBlockData(Schema):
    name: str
    identifier: str
    is_shared: bool = False
    site_slot: str = ""
    slot_order: int = 0
    render_in_preview: bool = True
    source_app: str = ""
    page_types: list[str] = []
    block_schema: str | list = Field([], alias="schema_json")


class PushVariantData(Schema):
    name: str
    identifier: str
    is_default: bool = False
    description: str = ""
    html: str = ""
    css: str = ""
    js: str = ""
    preview_desktop_light_url: str | None = None
    preview_desktop_dark_url: str | None = None
    preview_tablet_light_url: str | None = None
    preview_tablet_dark_url: str | None = None
    preview_mobile_light_url: str | None = None
    preview_mobile_dark_url: str | None = None


class PushInstallEnvelope(Schema):
    collection: PushCollectionData | None = None
    block: PushBlockData
    variant: PushVariantData


class PushPayload(Schema):
    install: PushInstallEnvelope


class PushResponse(Schema):
    created: bool
    name: str


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
