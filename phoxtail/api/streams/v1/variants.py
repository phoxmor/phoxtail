"""``/api/streams/v1/variants`` — BlockVariant endpoints.

Endpoints:
- ``GET    /``                  — list, optional ``?block=``/``?collection=`` filters
- ``GET    /{variant_id}``      — detail by numeric PK, sets ETag header
- ``PUT    /{variant_id}``      — update by numeric PK, requires ``If-Match``
"""

from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError
from wagtail.images import get_image_model
from wagtail.search.backends import get_search_backend

from phoxtail.api.streams.v1._helpers import (
    build_variant_envelope,
    etag_matches,
    resolve_variant_by_pk,
    variant_detail,
    variant_etag,
    variant_summary,
)
from phoxtail.api.streams.v1.schemas import (
    Error,
    PushPayload,
    PushResponse,
    Variant,
    VariantCreate,
    VariantList,
    VariantUpdate,
)
from phoxtail.streams.models import Block, BlockVariant, VariantCollection

router = Router()


# Defined before /{variant_id}/ endpoints so Django's URL resolver matches
# /push/ first — Ninja uses string-type path converters, so {variant_id}
# would otherwise capture the literal "push" and return 405.
@router.post(
    "/push/",
    response={200: PushResponse, 400: Error},
    summary="Receive a pushed BlockVariant from a remote project",
)
def push_variant(request: HttpRequest, payload: PushPayload):
    from django.core.exceptions import ValidationError

    from phoxtail.streams.services.sync import apply_variant_envelope

    envelope = payload.install.model_dump()
    try:
        result = apply_variant_envelope(envelope)
    except ValidationError as exc:
        return 400, Error(detail=" ".join(exc.messages))
    return PushResponse(created=result.created, name=result.variant.name)


@router.get(
    "/",
    response={200: VariantList},
    summary="List BlockVariants",
)
def list_variants(
    request: HttpRequest,
    block: str | None = Query(None, description="Filter by block identifier."),
    collection: str | None = Query(None, description="Filter by collection identifier."),
    search: str | None = Query(None, description="Prefix search on variant name and identifier."),
):
    qs = BlockVariant.objects.select_related("block", "collection").prefetch_related("block__page_types").all()
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

    if BlockVariant.objects.filter(identifier=payload.identifier, block=block, collection=collection).exists():
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
    response={200: Variant, 404: Error, 409: Error, 412: Error, 428: Error},
    summary="Update a BlockVariant by numeric ID (optimistic concurrency)",
)
def update_variant_by_id(
    request: HttpRequest,
    response: HttpResponse,
    variant_id: int,
    payload: VariantUpdate,
):
    """Update a variant's fields, guarded by ``If-Match``."""
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this variant.",
        )

    v = resolve_variant_by_pk(variant_id)
    current = variant_etag(v)
    if not etag_matches(if_match, current):
        raise HttpError(
            412,
            "ETag mismatch: the variant has changed since you last read it. Re-fetch and retry.",
        )

    new_collection = v.collection
    if payload.collection_id is not None:
        try:
            new_collection = VariantCollection.objects.get(pk=payload.collection_id)
        except VariantCollection.DoesNotExist:
            raise HttpError(404, f"Collection {payload.collection_id} not found.")
        v.collection = new_collection

    new_identifier = payload.identifier if payload.identifier is not None else v.identifier
    if payload.identifier is not None:
        v.identifier = payload.identifier

    # Check uniqueness of (block, collection, identifier) if either changed.
    if payload.identifier is not None or payload.collection_id is not None:
        collision = (
            BlockVariant.objects.filter(
                block=v.block,
                collection=new_collection,
                identifier=new_identifier,
            )
            .exclude(pk=v.pk)
            .exists()
        )
        if collision:
            raise HttpError(
                409,
                f"Variant '{new_identifier}' already exists for block "
                f"'{v.block.identifier}' in collection "
                f"'{new_collection.identifier}'.",
            )

    if payload.name is not None:
        v.name = payload.name
    if payload.description is not None:
        v.description = payload.description
    if payload.html is not None:
        v.html = payload.html
    if payload.css is not None:
        v.css = payload.css
    if payload.javascript is not None:
        v.javascript = payload.javascript

    if "preview_image_id" in payload.model_fields_set:
        if payload.preview_image_id is None:
            v.preview_image = None
        else:
            Image = get_image_model()
            try:
                v.preview_image = Image.objects.get(pk=payload.preview_image_id)
            except Image.DoesNotExist:
                raise HttpError(404, f"Image {payload.preview_image_id} not found.")

    with transaction.atomic():
        if payload.is_default is True:
            BlockVariant.objects.filter(block=v.block, is_default=True).exclude(pk=v.pk).update(is_default=False)
            v.is_default = True
        elif payload.is_default is False:
            v.is_default = False
        v.save()

    response["ETag"] = variant_etag(v)
    return variant_detail(v)


@router.delete(
    "/{variant_id}/",
    response={204: None, 404: Error},
    summary="Delete a BlockVariant by numeric ID",
)
def delete_variant(request: HttpRequest, variant_id: int):
    v = resolve_variant_by_pk(variant_id)
    v.delete()
    return 204, None


@router.get(
    "/{variant_id}/pull/",
    summary="Pull a BlockVariant install payload",
)
def pull_variant(request: HttpRequest, variant_id: int):
    """Return the full install envelope for cross-project variant sync.

    Consumed by StreamsSyncService.pull() on the pulling project.
    """
    try:
        v = (
            BlockVariant.objects.select_related("block", "collection")
            .prefetch_related("block__page_types")
            .get(pk=variant_id)
        )
    except BlockVariant.DoesNotExist:
        raise HttpError(404, f"Variant {variant_id} not found.")

    return {
        "title": v.name,
        "description": v.description,
        "install": build_variant_envelope(v),
    }
