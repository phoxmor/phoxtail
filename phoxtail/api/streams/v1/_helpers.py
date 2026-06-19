"""Shared resolution and serialization helpers for the streams v1 routers.

These helpers keep the router modules thin: a router function resolves its
inputs, loads the ORM objects, and hands them off to a ``to_*`` serializer
that returns plain dicts matching the Pydantic schemas.

Nothing in this module imports Rich, Typer, or any CLI concern — the API
layer is pure Django/Ninja/Django ORM.
"""

from __future__ import annotations

import hashlib
import json

from ninja.errors import HttpError

from phoxtail.streams.models import (
    Block,
    BlockCategory,
    BlockVariant,
    SharedBlock,
    VariantCollection,
)
from phoxtail.streams.utils import _image_url

# ---------------------------------------------------------------------------
# Variant resolution
# ---------------------------------------------------------------------------


def resolve_variant_by_pk(pk: int) -> BlockVariant:
    """Resolve a ``BlockVariant`` by its numeric primary key."""
    try:
        return BlockVariant.objects.select_related("block", "collection").get(pk=pk)
    except BlockVariant.DoesNotExist as exc:
        raise HttpError(404, f"Variant {pk} not found.") from exc


def resolve_collection_by_pk(pk: int) -> VariantCollection:
    try:
        return VariantCollection.objects.get(pk=pk)
    except VariantCollection.DoesNotExist as exc:
        raise HttpError(404, f"Collection {pk} not found.") from exc


def resolve_block_by_pk(pk: int) -> Block:
    try:
        return Block.objects.prefetch_related("variants__collection", "page_types").get(pk=pk)
    except Block.DoesNotExist as exc:
        raise HttpError(404, f"Block {pk} not found.") from exc


def resolve_collection(identifier: str) -> VariantCollection:
    try:
        return VariantCollection.objects.get(identifier=identifier)
    except VariantCollection.DoesNotExist as exc:
        raise HttpError(404, f"Collection '{identifier}' not found.") from exc


def resolve_block(identifier: str) -> Block:
    try:
        return Block.objects.prefetch_related("variants__collection", "page_types").get(identifier=identifier)
    except Block.DoesNotExist as exc:
        raise HttpError(404, f"Block '{identifier}' not found.") from exc


# ---------------------------------------------------------------------------
# Serializers (model → dict matching Pydantic schemas)
# ---------------------------------------------------------------------------


def build_variant_envelope(v: BlockVariant) -> dict:
    """Build the cross-project sync envelope for a BlockVariant.

    Used by ``GET /{id}/pull/`` and by ``StreamsSyncService.push()``.
    Caller must ensure ``block__page_types`` is prefetched.
    """
    b = v.block
    return {
        "collection": ({"name": v.collection.name, "identifier": v.collection.identifier} if v.collection_id else None),
        "block": {
            "name": b.name,
            "identifier": b.identifier,
            "is_shared": b.is_shared,
            "source_app": b.source_app,
            "page_types": [f"{ct.app_label}.{ct.model}" for ct in b.page_types.all()],
            "schema_json": b.schema.get_prep_value(),
        },
        "variant": {
            "name": v.name,
            "identifier": v.identifier,
            "is_default": v.is_default,
            "description": v.description,
            "html": v.html,
            "css": v.css,
            "js": v.javascript,
            "preview_desktop_light_url": _image_url(v.preview_image_desktop) or "",
            "preview_desktop_dark_url": _image_url(v.preview_image_desktop_dark) or "",
            "preview_tablet_light_url": _image_url(v.preview_image_tablet) or "",
            "preview_tablet_dark_url": _image_url(v.preview_image_tablet_dark) or "",
            "preview_mobile_light_url": _image_url(v.preview_image_mobile) or "",
            "preview_mobile_dark_url": _image_url(v.preview_image_mobile_dark) or "",
        },
    }


def variant_summary(v: BlockVariant) -> dict:
    return {
        "id": v.id,
        "identifier": v.identifier,
        "name": v.name,
        "description": v.description,
        "is_default": v.is_default,
        "block": {
            "id": v.block.id,
            "identifier": v.block.identifier,
            "name": v.block.name,
            "source_app": v.block.source_app,
            "page_types": [f"{ct.app_label}.{ct.model}" for ct in v.block.page_types.all()],
        },
        "collection": (
            {"id": v.collection.id, "identifier": v.collection.identifier, "name": v.collection.name}
            if v.collection_id
            else None
        ),
        "preview_desktop_light_url": _image_url(v.preview_image_desktop) or "",
        "preview_desktop_dark_url": _image_url(v.preview_image_desktop_dark) or "",
        "preview_tablet_light_url": _image_url(v.preview_image_tablet) or "",
        "preview_tablet_dark_url": _image_url(v.preview_image_tablet_dark) or "",
        "preview_mobile_light_url": _image_url(v.preview_image_mobile) or "",
        "preview_mobile_dark_url": _image_url(v.preview_image_mobile_dark) or "",
    }


def variant_detail(v: BlockVariant) -> dict:
    return {
        **variant_summary(v),
        "html": v.html,
        "css": v.css,
        "javascript": v.javascript,
    }


def collection_summary(c: VariantCollection, variant_count: int) -> dict:
    return {
        "id": c.id,
        "identifier": c.identifier,
        "name": c.name,
        "description": c.description,
        "variant_count": variant_count,
    }


def collection_detail(c: VariantCollection, variant_count: int) -> dict:
    return collection_summary(c, variant_count)


def block_summary(b: Block, variant_count: int) -> dict:
    return {
        "id": b.id,
        "identifier": b.identifier,
        "name": b.name,
        "description": b.description,
        "group": b.group,
        "icon": b.icon,
        "is_shared": b.is_shared,
        "source_app": b.source_app,
        "variant_count": variant_count,
    }


def block_detail(b: Block) -> dict:
    variants = [
        {
            "id": v.id,
            "identifier": v.identifier,
            "name": v.name,
            "is_default": v.is_default,
            "collection": (
                {"id": v.collection.id, "identifier": v.collection.identifier, "name": v.collection.name}
                if v.collection_id
                else None
            ),
        }
        for v in b.variants.all()
    ]
    return {
        **block_summary(b, len(variants)),
        "page_types": [f"{ct.app_label}.{ct.model}" for ct in b.page_types.all()],
        "variants": variants,
        "field_schema": json.dumps(b.schema.get_prep_value(), indent=2),
        "sort_order": b.sort_order or 0,
    }


# ---------------------------------------------------------------------------
# ETags
# ---------------------------------------------------------------------------


def variant_etag(v: BlockVariant) -> str:
    """Compute a weak ETag covering all mutable variant fields.

    Includes metadata (identifier, name, description, collection, is_default,
    all six preview image FKs) as well as content (html, css, javascript) so that any
    update — not just content edits — invalidates a stale If-Match header.
    """
    h = hashlib.sha256()
    for part in (
        v.identifier,
        v.name,
        v.description,
        str(v.collection_id),
        str(v.is_default),
        str(v.preview_image_desktop_id or ""),
        str(v.preview_image_desktop_dark_id or ""),
        str(v.preview_image_tablet_id or ""),
        str(v.preview_image_tablet_dark_id or ""),
        str(v.preview_image_mobile_id or ""),
        str(v.preview_image_mobile_dark_id or ""),
        v.html,
        v.css,
        v.javascript,
    ):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def etag_matches(header_value: str | None, current: str) -> bool:
    """Check ``If-Match`` semantics tolerantly.

    Treats ``W/"abc"`` and ``"abc"`` as equivalent, per RFC 7232: weak
    validators are acceptable on non-range update requests.
    """
    if not header_value:
        return False
    candidates = {tag.strip() for tag in header_value.split(",")}
    normalized = {_strip_weak_prefix(t) for t in candidates}
    return _strip_weak_prefix(current) in normalized or "*" in candidates


def _strip_weak_prefix(tag: str) -> str:
    return tag[2:] if tag.startswith("W/") else tag


# ---------------------------------------------------------------------------
# Block ETags
# ---------------------------------------------------------------------------


def collection_etag(c: VariantCollection) -> str:
    """Compute a weak ETag for a collection's mutable fields."""
    h = hashlib.sha256()
    for field in (c.name, c.identifier, c.description):
        h.update(field.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def block_etag(b: Block) -> str:
    """Compute a weak ETag for a block's schema and metadata."""
    h = hashlib.sha256()
    fields = (
        b.name,
        b.identifier,
        b.description,
        b.icon,
        b.group,
        str(b.is_shared),
        str(b.sort_order or 0),
    )
    for field in fields:
        h.update(field.encode("utf-8"))
        h.update(b"\x00")
    h.update(json.dumps(b.schema.get_prep_value(), sort_keys=True).encode("utf-8"))
    return f'W/"{h.hexdigest()[:16]}"'


# ---------------------------------------------------------------------------
# SharedBlock resolution and serialization
# ---------------------------------------------------------------------------


def resolve_shared_block_by_pk(pk: int) -> SharedBlock:
    try:
        return SharedBlock.objects.select_related("block", "site", "locale").get(pk=pk)
    except SharedBlock.DoesNotExist as exc:
        raise HttpError(404, f"SharedBlock {pk} not found.") from exc


def resolve_site(pk: int):
    from wagtail.models import Site

    try:
        return Site.objects.get(pk=pk)
    except Site.DoesNotExist as exc:
        raise HttpError(404, f"Site {pk} not found.") from exc


def resolve_locale(pk: int):
    from wagtail.models import Locale

    try:
        return Locale.objects.get(pk=pk)
    except Locale.DoesNotExist as exc:
        raise HttpError(404, f"Locale {pk} not found.") from exc


def shared_block_summary(sb: SharedBlock) -> dict:
    return {
        "id": sb.id,
        "block_id": sb.block_id,
        "block": {
            "id": sb.block.id,
            "identifier": sb.block.identifier,
            "name": sb.block.name,
        },
        "site_id": sb.site_id,
        "site_hostname": sb.site.hostname,
        "locale_id": sb.locale_id,
        "language_code": sb.locale.language_code,
        "created_at": sb.created_at.isoformat(),
        "updated_at": sb.updated_at.isoformat(),
    }


def shared_block_detail(sb: SharedBlock) -> dict:
    return {
        **shared_block_summary(sb),
        "content": json.dumps(sb.content.get_prep_value() or [], indent=2),
    }


def shared_block_etag(sb: SharedBlock) -> str:
    h = hashlib.sha256()
    for part in (
        str(sb.block_id),
        str(sb.site_id),
        str(sb.locale_id),
        json.dumps(sb.content.get_prep_value() or [], sort_keys=True),
        sb.updated_at.isoformat(),
    ):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


# ---------------------------------------------------------------------------
# BlockCategory resolution and serialization
# ---------------------------------------------------------------------------


def resolve_block_category_by_pk(pk: int) -> BlockCategory:
    try:
        return BlockCategory.objects.get(pk=pk)
    except BlockCategory.DoesNotExist as exc:
        raise HttpError(404, f"BlockCategory {pk} not found.") from exc


def block_category_detail(c: BlockCategory) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
    }


def block_category_etag(c: BlockCategory) -> str:
    h = hashlib.sha256()
    for field in (c.name, c.slug, c.description):
        h.update(field.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


# ---------------------------------------------------------------------------
# Page-type resolution
# ---------------------------------------------------------------------------


def resolve_page_types(page_type_strings: list[str]) -> list:
    """Convert ``["blog.BlogPage", ...]`` to ContentType objects.

    Raises ``HttpError(400)`` for invalid entries.
    """
    from django.contrib.contenttypes.models import ContentType

    content_types = []
    for app_model in page_type_strings:
        try:
            app_label, model_name = app_model.rsplit(".", 1)
            ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
            content_types.append(ct)
        except (ValueError, ContentType.DoesNotExist):
            raise HttpError(400, f"Invalid page type: '{app_model}'.")
    return content_types
