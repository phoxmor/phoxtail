"""``/api/streams/v1/variants`` — BlockVariant endpoints.

Endpoints:
- ``GET    /``              — list, optional ``?block=``/``?collection=`` filters
- ``GET    /{identifier}``  — detail, sets ETag header
- ``PUT    /{identifier}``  — update, requires ``If-Match`` precondition

The variant identifier is unique only within a (block, collection) pair,
so every single-variant endpoint accepts ``?block=`` and ``?collection=``
query params as disambiguators.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError

from phoxtail.api.streams.v1._helpers import (
    etag_matches,
    resolve_variant,
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
):
    qs = BlockVariant.objects.select_related("block", "collection").all()
    if block:
        qs = qs.filter(block__identifier=block)
    if collection:
        qs = qs.filter(collection__identifier=collection)

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
        block = Block.objects.get(identifier=payload.block)
    except Block.DoesNotExist:
        raise HttpError(404, f"Block '{payload.block}' not found.")
    try:
        collection = VariantCollection.objects.get(identifier=payload.collection)
    except VariantCollection.DoesNotExist:
        raise HttpError(404, f"Collection '{payload.collection}' not found.")

    if BlockVariant.objects.filter(
        identifier=payload.identifier, block=block, collection=collection
    ).exists():
        raise HttpError(
            409,
            f"Variant '{payload.identifier}' already exists "
            f"in {block.identifier}/{collection.identifier}.",
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
    )
    response.status_code = 201
    response["ETag"] = variant_etag(v)
    return variant_detail(v)


@router.get(
    "/{identifier}/",
    response={200: Variant, 404: Error, 409: Error},
    summary="Show a BlockVariant",
)
def get_variant(
    request: HttpRequest,
    response: HttpResponse,
    identifier: str,
    block: str | None = Query(None, description="Disambiguate by block identifier."),
    collection: str | None = Query(
        None, description="Disambiguate by collection identifier."
    ),
):
    v = resolve_variant(identifier, block=block, collection=collection)
    response["ETag"] = variant_etag(v)
    return variant_detail(v)


@router.put(
    "/{identifier}/",
    response={200: Variant, 404: Error, 409: Error, 412: Error, 428: Error},
    summary="Update a BlockVariant (optimistic concurrency)",
)
def update_variant(
    request: HttpRequest,
    response: HttpResponse,
    identifier: str,
    payload: VariantUpdate,
    block: str | None = Query(None, description="Disambiguate by block identifier."),
    collection: str | None = Query(
        None, description="Disambiguate by collection identifier."
    ),
):
    """Update a variant's content, guarded by ``If-Match``.

    Callers must send an ``If-Match`` header containing the ETag they saw
    on their most recent ``GET``. A mismatch returns 412; a missing header
    returns 428 (Precondition Required). On success the new ETag is set
    on the response so the caller can keep updating.
    """
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most "
            "recent GET of this variant.",
        )

    v = resolve_variant(identifier, block=block, collection=collection)
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
    v.save()

    response["ETag"] = variant_etag(v)
    return variant_detail(v)
