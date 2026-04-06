"""``/api/streams/v1/collections`` — VariantCollection endpoints."""

from __future__ import annotations

from django.db.models import Count
from django.http import HttpRequest
from ninja import Router

from phoxtail.api.streams.v1._helpers import (
    collection_detail,
    collection_summary,
    resolve_collection,
)
from phoxtail.api.streams.v1.schemas import (
    Collection,
    CollectionList,
    CollectionRendered,
    Error,
)
from phoxtail.streams.models import VariantCollection

router = Router()


@router.get("/", response={200: CollectionList}, summary="List VariantCollections")
def list_collections(request: HttpRequest):
    qs = VariantCollection.objects.annotate(
        _variant_count=Count("variants", distinct=True)
    ).order_by("name")
    collections = [collection_summary(c, c._variant_count) for c in qs]
    return {"collections": collections, "total": len(collections)}


@router.get(
    "/{identifier}/",
    response={200: Collection, 404: Error},
    summary="Show a VariantCollection",
)
def get_collection(request: HttpRequest, identifier: str):
    c = resolve_collection(identifier)
    return collection_detail(c, c.variants.count())


@router.post(
    "/{identifier}/render/",
    response={200: CollectionRendered, 404: Error},
    summary="Render a collection's design tokens",
)
def render_collection(request: HttpRequest, identifier: str):
    """Render a collection's DTL template into design tokens.

    Returns the collection metadata plus the fully rendered design
    tokens — palette roles, font roles, color strategy, and typography
    guidelines. This is the version AI agents should consume.
    """
    c = resolve_collection(identifier)
    return {
        "identifier": c.identifier,
        "name": c.name,
        "description": c.description,
        "design_tokens": c.render(),
    }
