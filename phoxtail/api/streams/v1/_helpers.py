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
    BlockVariant,
    VariantCollection,
)

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
        return Block.objects.prefetch_related("variants__collection", "page_types").get(
            pk=pk
        )
    except Block.DoesNotExist as exc:
        raise HttpError(404, f"Block {pk} not found.") from exc


def resolve_collection(identifier: str) -> VariantCollection:
    try:
        return VariantCollection.objects.get(identifier=identifier)
    except VariantCollection.DoesNotExist as exc:
        raise HttpError(404, f"Collection '{identifier}' not found.") from exc


def resolve_block(identifier: str) -> Block:
    try:
        return Block.objects.prefetch_related("variants__collection", "page_types").get(
            identifier=identifier
        )
    except Block.DoesNotExist as exc:
        raise HttpError(404, f"Block '{identifier}' not found.") from exc


# ---------------------------------------------------------------------------
# Serializers (model → dict matching Pydantic schemas)
# ---------------------------------------------------------------------------


def variant_summary(v: BlockVariant) -> dict:
    return {
        "id": v.id,
        "identifier": v.identifier,
        "name": v.name,
        "description": v.description,
        "is_default": v.is_default,
        "block": {"identifier": v.block.identifier, "name": v.block.name},
        "collection": {
            "identifier": v.collection.identifier,
            "name": v.collection.name,
        },
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
    return {**collection_summary(c, variant_count), "template": c.template}


def block_summary(b: Block, variant_count: int) -> dict:
    return {
        "id": b.id,
        "identifier": b.identifier,
        "name": b.name,
        "description": b.description,
        "group": b.group,
        "icon": b.icon,
        "is_shared": b.is_shared,
        "variant_count": variant_count,
    }


def block_detail(b: Block) -> dict:
    variants = [
        {
            "id": v.id,
            "identifier": v.identifier,
            "name": v.name,
            "is_default": v.is_default,
            "collection": {
                "identifier": v.collection.identifier,
                "name": v.collection.name,
            },
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
    """Compute a weak ETag for a variant's content.

    Hashes the three content fields (html, css, javascript) and returns a
    16-hex-char prefix wrapped as a weak validator. Weak (``W/"..."``) is
    the right qualifier because the representation is a serialization of
    the content, not the bytes themselves — two semantically identical
    responses with different JSON whitespace should still match.

    This ETag is also the foundation for Phase 5's sync version field.
    """
    h = hashlib.sha256()
    h.update(v.html.encode("utf-8"))
    h.update(b"\x00")
    h.update(v.css.encode("utf-8"))
    h.update(b"\x00")
    h.update(v.javascript.encode("utf-8"))
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
    """Compute a weak ETag for a collection's content.

    Hashes the mutable content fields (name, description, template).
    """
    h = hashlib.sha256()
    for field in (c.name, c.identifier, c.description, c.template):
        h.update(field.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def block_etag(b: Block) -> str:
    """Compute a weak ETag for a block's schema and metadata."""
    h = hashlib.sha256()
    fields = (b.name, b.identifier, b.description, b.icon, b.group, str(b.is_shared))
    for field in fields:
        h.update(field.encode("utf-8"))
        h.update(b"\x00")
    h.update(json.dumps(b.schema.get_prep_value(), sort_keys=True).encode("utf-8"))
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
