"""``/api/streams/v1/shared-blocks`` — SharedBlock endpoints."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError

from phoxtail.api.streams.v1._helpers import (
    etag_matches,
    resolve_block_by_pk,
    resolve_locale,
    resolve_shared_block_by_pk,
    resolve_site,
    shared_block_detail,
    shared_block_etag,
    shared_block_summary,
)
from phoxtail.api.streams.v1.schemas import (
    Error,
    SharedBlock,
    SharedBlockCreate,
    SharedBlockList,
    SharedBlockUpdate,
)
from phoxtail.streams.models import SharedBlock as SharedBlockModel

router = Router()


@router.get("/", response={200: SharedBlockList}, summary="List SharedBlocks")
def list_shared_blocks(
    request: HttpRequest,
    block: int | None = Query(None, description="Filter by block ID."),
    site: int | None = Query(None, description="Filter by site ID."),
    locale: int | None = Query(None, description="Filter by locale ID."),
):
    qs = SharedBlockModel.objects.select_related("block", "site", "locale").order_by(
        "block__name", "site__hostname", "locale__language_code"
    )
    if block is not None:
        qs = qs.filter(block_id=block)
    if site is not None:
        qs = qs.filter(site_id=site)
    if locale is not None:
        qs = qs.filter(locale_id=locale)
    results = [shared_block_summary(sb) for sb in qs]
    return {"shared_blocks": results, "total": len(results)}


@router.get(
    "/{shared_block_id}/",
    response={200: SharedBlock, 404: Error},
    summary="Show a SharedBlock by numeric ID",
)
def get_shared_block_by_id(request: HttpRequest, response: HttpResponse, shared_block_id: int):
    sb = resolve_shared_block_by_pk(shared_block_id)
    response["ETag"] = shared_block_etag(sb)
    return shared_block_detail(sb)


@router.post(
    "/",
    response={201: SharedBlock, 400: Error, 404: Error, 409: Error},
    summary="Create a SharedBlock",
)
def create_shared_block(request: HttpRequest, response: HttpResponse, payload: SharedBlockCreate):
    block = resolve_block_by_pk(payload.block_id)
    if not block.is_shared:
        raise HttpError(
            400,
            f"Block '{block.identifier}' does not have is_shared enabled.",
        )
    site = resolve_site(payload.site_id)
    locale = resolve_locale(payload.locale_id)

    sb = SharedBlockModel(block=block, site=site, locale=locale)
    if payload.content:
        sb.content = payload.content

    try:
        sb.full_clean()
    except ValidationError as exc:
        raise HttpError(400, _format_validation_error(exc))

    try:
        sb.save()
    except IntegrityError:
        raise HttpError(
            409,
            f"A SharedBlock for block {payload.block_id}, site {payload.site_id}, "
            f"locale {payload.locale_id} already exists.",
        )

    sb = resolve_shared_block_by_pk(sb.pk)
    response["ETag"] = shared_block_etag(sb)
    return 201, shared_block_detail(sb)


@router.patch(
    "/{shared_block_id}/",
    response={200: SharedBlock, 400: Error, 404: Error, 412: Error, 428: Error},
    summary="Update a SharedBlock's content by numeric ID",
)
def update_shared_block_by_id(
    request: HttpRequest,
    response: HttpResponse,
    shared_block_id: int,
    payload: SharedBlockUpdate,
):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this shared block.",
        )

    sb = resolve_shared_block_by_pk(shared_block_id)
    current = shared_block_etag(sb)

    if not etag_matches(if_match, current):
        raise HttpError(
            412,
            "ETag mismatch: the shared block has changed since you last read it. Re-fetch and retry.",
        )

    if payload.content is not None:
        sb.content = payload.content

    try:
        sb.full_clean()
    except ValidationError as exc:
        raise HttpError(400, _format_validation_error(exc))

    sb.save()

    sb = resolve_shared_block_by_pk(shared_block_id)
    response["ETag"] = shared_block_etag(sb)
    return shared_block_detail(sb)


@router.delete(
    "/{shared_block_id}/",
    response={204: None, 404: Error},
    summary="Delete a SharedBlock by numeric ID",
)
def delete_shared_block_by_id(request: HttpRequest, shared_block_id: int):
    sb = resolve_shared_block_by_pk(shared_block_id)
    sb.delete()
    return 204, None


def _format_validation_error(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{k}: {', '.join(v)}" if isinstance(v, list) else f"{k}: {v}" for k, v in exc.message_dict.items()
        )
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
