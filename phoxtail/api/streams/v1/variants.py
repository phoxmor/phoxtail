"""``/api/streams/v1/variants`` — BlockVariant endpoints.

Endpoints:
- ``GET    /``                  — list, optional ``?block=``/``?collection=`` filters
- ``GET    /{variant_id}``      — detail by numeric PK, sets ETag header
- ``PUT    /{variant_id}``      — update by numeric PK, requires ``If-Match``
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.streams.v1._helpers import (
    etag_matches,
    resolve_variant_by_pk,
    variant_detail,
    variant_etag,
    variant_summary,
)
from phoxtail.api.streams.v1.schemas import (
    Error,
    Variant,
    VariantCreate,
    VariantList,
    VariantUpdate,
)
from phoxtail.streams.models import Block, BlockVariant, VariantCollection

router = Router()


@router.get(
    "/",
    response={200: VariantList},
    summary="List BlockVariants",
)
def list_variants(
    request: HttpRequest,
    block: str | None = Query(None, description="Filter by block identifier."),
    collection: str | None = Query(
        None, description="Filter by collection identifier."
    ),
    search: str | None = Query(
        None, description="Prefix search on variant name and identifier."
    ),
):
    qs = BlockVariant.objects.select_related("block", "collection").all()
    if block:
        qs = qs.filter(block__identifier=block)
    if collection:
        qs = qs.filter(collection__identifier=collection)
    if search:
        qs = get_search_backend().autocomplete(search, qs)

    variants = [variant_summary(v) for v in qs]
    return {"variants": variants, "total": len(variants)}


@router.post(
    "/",
    response={201: Variant, 400: Error, 404: Error, 409: Error},
    summary="Create a BlockVariant",
)
def create_variant(
    request: HttpRequest,
    response: HttpResponse,
    payload: VariantCreate,
):
    try:
        block = Block.objects.get(pk=payload.block_id)
    except Block.DoesNotExist:
        raise HttpError(404, f"Block {payload.block_id} not found.")
    try:
        collection = VariantCollection.objects.get(pk=payload.collection_id)
    except VariantCollection.DoesNotExist:
        raise HttpError(404, f"Collection {payload.collection_id} not found.")

    if BlockVariant.objects.filter(
        identifier=payload.identifier, block=block, collection=collection
    ).exists():
        raise HttpError(
            409,
            f"Variant '{payload.identifier}' already exists "
            f"for block {payload.block_id}/collection {payload.collection_id}.",
        )

    v = BlockVariant.objects.create(
        identifier=payload.identifier,
        name=payload.name,
        block=block,
        collection=collection,
        description=payload.description,
        html=payload.html,
        css=payload.css,
        javascript=payload.javascript,
        is_default=payload.is_default,
    )
    response["ETag"] = variant_etag(v)
    return 201, variant_detail(v)


@router.get(
    "/{variant_id}/",
    response={200: Variant, 404: Error},
    summary="Show a BlockVariant by numeric ID",
)
def get_variant_by_id(
    request: HttpRequest,
    response: HttpResponse,
    variant_id: int,
):
    v = resolve_variant_by_pk(variant_id)
    response["ETag"] = variant_etag(v)
    return variant_detail(v)


@router.put(
    "/{variant_id}/",
    response={200: Variant, 404: Error, 412: Error, 428: Error},
    summary="Update a BlockVariant by numeric ID (optimistic concurrency)",
)
def update_variant_by_id(
    request: HttpRequest,
    response: HttpResponse,
    variant_id: int,
    payload: VariantUpdate,
):
    """Update a variant's content, guarded by ``If-Match``."""
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most "
            "recent GET of this variant.",
        )

    v = resolve_variant_by_pk(variant_id)
    current = variant_etag(v)
    if not etag_matches(if_match, current):
        raise HttpError(
            412,
            "ETag mismatch: the variant has changed since you last read it. "
            "Re-fetch and retry.",
        )

    if payload.html is not None:
        v.html = payload.html
    if payload.css is not None:
        v.css = payload.css
    if payload.javascript is not None:
        v.javascript = payload.javascript
    if payload.is_default is not None:
        v.is_default = payload.is_default
    v.save()

    response["ETag"] = variant_etag(v)
    return variant_detail(v)
