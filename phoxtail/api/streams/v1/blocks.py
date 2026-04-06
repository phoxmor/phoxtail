"""``/api/streams/v1/blocks`` — Block endpoints."""

from __future__ import annotations

from django.db.models import Count
from django.http import HttpRequest
from ninja import Router

from phoxtail.api.streams.v1._helpers import (
    block_detail,
    block_summary,
    resolve_block,
)
from phoxtail.api.streams.v1.schemas import (
    Block,
    BlockList,
    Error,
)
from phoxtail.streams.models import Block as BlockModel

router = Router()


@router.get("/", response={200: BlockList}, summary="List Blocks")
def list_blocks(request: HttpRequest):
    qs = BlockModel.objects.annotate(
        _variant_count=Count("variants", distinct=True)
    ).order_by("group", "name")
    blocks = [block_summary(b, b._variant_count) for b in qs]
    return {"blocks": blocks, "total": len(blocks)}


@router.get(
    "/{identifier}/",
    response={200: Block, 404: Error},
    summary="Show a Block",
)
def get_block(request: HttpRequest, identifier: str):
    b = resolve_block(identifier)
    return block_detail(b)
