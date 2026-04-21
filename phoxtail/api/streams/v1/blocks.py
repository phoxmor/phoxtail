"""``/api/streams/v1/blocks`` — Block endpoints."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.streams.v1._helpers import (
    block_detail,
    block_etag,
    block_summary,
    etag_matches,
    resolve_block,
    resolve_page_types,
)
from phoxtail.api.streams.v1.schemas import (
    Block,
    BlockCreate,
    BlockList,
    BlockUpdate,
    Error,
)
from phoxtail.streams.models import Block as BlockModel

router = Router()


@router.get("/", response={200: BlockList}, summary="List Blocks")
def list_blocks(
    request: HttpRequest,
    search: str | None = Query(
        None, description="Prefix search on block name and identifier."
    ),
):
    qs = BlockModel.objects.annotate(
        _variant_count=Count("variants", distinct=True)
    ).order_by("group", "name")
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    blocks = [block_summary(b, b._variant_count) for b in qs]
    return {"blocks": blocks, "total": len(blocks)}


@router.get(
    "/{identifier}/",
    response={200: Block, 404: Error},
    summary="Show a Block",
)
def get_block(request: HttpRequest, response: HttpResponse, identifier: str):
    b = resolve_block(identifier)
    response["ETag"] = block_etag(b)
    return block_detail(b)


@router.post(
    "/",
    response={201: Block, 400: Error, 409: Error},
    summary="Create a Block",
)
def create_block(request: HttpRequest, response: HttpResponse, payload: BlockCreate):
    b = BlockModel(
        identifier=payload.identifier,
        name=payload.name,
        description=payload.description,
        icon=payload.icon,
        group=payload.group,
        is_shared=payload.is_shared,
        schema=payload.block_schema,
        sort_order=payload.sort_order,
    )

    try:
        b.full_clean()
    except ValidationError as exc:
        detail = _format_validation_error(exc)
        raise HttpError(400, detail)

    try:
        b.save()
    except IntegrityError:
        raise HttpError(409, f"Block '{payload.identifier}' already exists.")

    if payload.page_types:
        b.page_types.set(resolve_page_types(payload.page_types))

    # Re-fetch with prefetches for block_detail serialization
    b = resolve_block(b.identifier)
    response["ETag"] = block_etag(b)
    return 201, block_detail(b)


@router.patch(
    "/{identifier}/",
    response={200: Block, 400: Error, 404: Error, 412: Error, 428: Error},
    summary="Update a Block",
)
def update_block(
    request: HttpRequest,
    response: HttpResponse,
    identifier: str,
    payload: BlockUpdate,
):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most "
            "recent GET of this block.",
        )

    b = resolve_block(identifier)
    current = block_etag(b)

    if not etag_matches(if_match, current):
        raise HttpError(
            412,
            "ETag mismatch: the block has changed since you last read it. "
            "Re-fetch and retry.",
        )

    # Apply non-None fields
    if payload.name is not None:
        b.name = payload.name
    if payload.description is not None:
        b.description = payload.description
    if payload.icon is not None:
        b.icon = payload.icon
    if payload.group is not None:
        b.group = payload.group
    if payload.is_shared is not None:
        b.is_shared = payload.is_shared
    if payload.block_schema is not None:
        b.schema = payload.block_schema

    try:
        b.full_clean()
    except ValidationError as exc:
        detail = _format_validation_error(exc)
        raise HttpError(400, detail)

    b.save()

    if payload.page_types is not None:
        b.page_types.set(resolve_page_types(payload.page_types))

    # Re-fetch for clean serialization
    b = resolve_block(b.identifier)
    response["ETag"] = block_etag(b)
    return block_detail(b)


def _format_validation_error(exc: ValidationError) -> str:
    """Extract a human-readable string from a Django ``ValidationError``."""
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{k}: {', '.join(v)}" if isinstance(v, list) else f"{k}: {v}"
            for k, v in exc.message_dict.items()
        )
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
