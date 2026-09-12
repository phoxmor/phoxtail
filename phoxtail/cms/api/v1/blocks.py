"""``/api/cms/v1/pages/{page_id}/blocks/`` — per-block CRUD endpoints.

All mutating endpoints require an ``If-Match`` ETag header (page-level ETag),
create a draft revision, and do **not** publish.

HTML render endpoints for HTMX live in ``phoxtail.cms.views`` (Django views
with session auth), not here.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from ninja.errors import HttpError

from phoxtail.cms.api.v1._helpers import (
    body_field_name_for,
    page_etag,
    replace_body,
    require_edit_permission,
    require_if_match,
    resolve_page,
    resolve_page_for_read,
    serialize_body,
)

router = Router()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class BlockUpdate(Schema):
    """Request body for ``PATCH /pages/{page_id}/blocks/{block_uuid}/``."""

    value: dict[str, Any]


class BlockPosition(Schema):
    """Exactly one of these must be set."""

    before_uuid: str | None = None
    after_uuid: str | None = None
    index: int | None = None

    def validate_exclusive(self) -> None:
        set_fields = [k for k in ("before_uuid", "after_uuid", "index") if getattr(self, k) is not None]
        if len(set_fields) > 1:
            raise HttpError(
                400,
                f"Specify exactly one of before_uuid / after_uuid / index; got: {set_fields}",
            )


class BlockAdd(Schema):
    """Request body for ``POST /pages/{page_id}/blocks/``."""

    type: str
    value: dict[str, Any]
    position: BlockPosition | None = None


class BlockMove(Schema):
    """Request body for ``POST /pages/{page_id}/blocks/{block_uuid}/move/``."""

    position: BlockPosition


class BlockItem(Schema):
    """A single serialized StreamField block."""

    type: str
    value: dict[str, Any]
    id: str


class BlockResponse(Schema):
    block: BlockItem


class BlockDeleted(Schema):
    deleted_uuid: str


class BlockMoved(Schema):
    moved_uuid: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_block(body: list[dict[str, Any]], uuid: str) -> tuple[int, dict[str, Any]]:
    """Return ``(index, block_dict)`` for the block with the given UUID.

    Raises 404 if not found.
    """
    for i, block in enumerate(body):
        if block.get("id") == uuid:
            return i, block
    raise HttpError(404, f"Block '{uuid}' not found on this page.")


def _resolve_position(
    body: list[dict[str, Any]],
    position: BlockPosition | None,
    exclude_uuid: str | None = None,
) -> int:
    """Return the target insertion index from a BlockPosition.

    ``exclude_uuid`` is used for move: the block being moved is temporarily
    removed, so anchor UUIDs are resolved against the filtered list.
    """
    working = [b for b in body if b.get("id") != exclude_uuid]

    if position is None:
        return len(working)  # append

    if position.index is not None:
        idx = position.index
        if idx < 0 or idx > len(working):
            raise HttpError(400, f"index {idx} out of range (body has {len(working)} blocks).")
        return idx

    if position.after_uuid is not None:
        for i, b in enumerate(working):
            if b.get("id") == position.after_uuid:
                return i + 1
        raise HttpError(404, f"after_uuid '{position.after_uuid}' not found on this page.")

    if position.before_uuid is not None:
        for i, b in enumerate(working):
            if b.get("id") == position.before_uuid:
                return i
        raise HttpError(404, f"before_uuid '{position.before_uuid}' not found on this page.")

    return len(working)  # all None → append


def _commit_body(
    page,
    new_body: list[dict[str, Any]],
    field_name: str,
    request: HttpRequest,
    response: HttpResponse,
) -> str:
    """Replace body, save draft revision, set ETag header.  Returns fresh ETag."""
    with transaction.atomic():
        replace_body(page, new_body, field_name)
        page.save_revision(user=request.auth.user)
    etag = page_etag(page)
    response["ETag"] = etag
    return etag


# ---------------------------------------------------------------------------
# GET /pages/{page_id}/blocks/{block_uuid}/
# ---------------------------------------------------------------------------


@router.get(
    "/{page_id}/blocks/{block_uuid}/",
    response={200: dict, 404: dict},
    summary="Get a single block by UUID",
)
def get_block(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    block_uuid: str,
):
    live = resolve_page(page_id)
    response["ETag"] = page_etag(live)
    draft = resolve_page_for_read(page_id)
    body = serialize_body(draft, body_field_name_for(draft))
    _, block = _find_block(body, block_uuid)
    return {"block": block, "_etag": response["ETag"]}


# ---------------------------------------------------------------------------
# PATCH /pages/{page_id}/blocks/{block_uuid}/
# ---------------------------------------------------------------------------


@router.patch(
    "/{page_id}/blocks/{block_uuid}/",
    response={200: dict, 400: dict, 403: dict, 404: dict, 412: dict, 428: dict},
    summary="Update a single block's value (creates a draft revision)",
)
def patch_block(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    block_uuid: str,
    payload: BlockUpdate,
):
    page = resolve_page(page_id)
    require_edit_permission(request, page)
    require_if_match(request, page)

    field_name = body_field_name_for(page)
    body = serialize_body(resolve_page_for_read(page_id), field_name)
    idx, existing = _find_block(body, block_uuid)

    updated_block = {**existing, "value": payload.value}
    new_body = body[:idx] + [updated_block] + body[idx + 1 :]

    replace_body(page, new_body, field_name)
    canonical_body = serialize_body(page, field_name)
    _, saved_block = _find_block(canonical_body, block_uuid)
    with transaction.atomic():
        page.save_revision(user=request.auth.user)
    etag = page_etag(page)
    response["ETag"] = etag
    return {"block": saved_block, "_etag": etag}


# ---------------------------------------------------------------------------
# POST /pages/{page_id}/blocks/
# ---------------------------------------------------------------------------


@router.post(
    "/{page_id}/blocks/",
    response={201: dict, 400: dict, 403: dict, 404: dict, 412: dict, 428: dict},
    summary="Add a new block to the body (creates a draft revision)",
)
def add_block(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    payload: BlockAdd,
):
    if payload.position is not None:
        payload.position.validate_exclusive()

    page = resolve_page(page_id)
    require_edit_permission(request, page)
    require_if_match(request, page)

    field_name = body_field_name_for(page)
    body = serialize_body(resolve_page_for_read(page_id), field_name)

    new_uuid = str(uuid.uuid4())
    new_block: dict[str, Any] = {
        "type": payload.type,
        "value": payload.value,
        "id": new_uuid,
    }

    insert_at = _resolve_position(body, payload.position)
    new_body = body[:insert_at] + [new_block] + body[insert_at:]

    replace_body(page, new_body, field_name)
    canonical_body = serialize_body(page, field_name)
    _, saved_block = _find_block(canonical_body, new_uuid)
    with transaction.atomic():
        page.save_revision(user=request.auth.user)
    etag = page_etag(page)
    response["ETag"] = etag
    response.status_code = 201
    return 201, {"block": saved_block, "_etag": etag}


# ---------------------------------------------------------------------------
# DELETE /pages/{page_id}/blocks/{block_uuid}/
# ---------------------------------------------------------------------------


@router.delete(
    "/{page_id}/blocks/{block_uuid}/",
    response={200: dict, 403: dict, 404: dict, 412: dict, 428: dict},
    summary="Remove a block from the body (creates a draft revision)",
)
def delete_block(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    block_uuid: str,
):
    page = resolve_page(page_id)
    require_edit_permission(request, page)
    require_if_match(request, page)

    field_name = body_field_name_for(page)
    body = serialize_body(resolve_page_for_read(page_id), field_name)
    idx, _ = _find_block(body, block_uuid)

    new_body = body[:idx] + body[idx + 1 :]
    etag = _commit_body(page, new_body, field_name, request, response)
    return {"deleted_uuid": block_uuid, "_etag": etag}


# ---------------------------------------------------------------------------
# POST /pages/{page_id}/blocks/{block_uuid}/move/
# ---------------------------------------------------------------------------


@router.post(
    "/{page_id}/blocks/{block_uuid}/move/",
    response={200: dict, 400: dict, 403: dict, 404: dict, 412: dict, 428: dict},
    summary="Reorder a block within the body (creates a draft revision)",
)
def move_block(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    block_uuid: str,
    payload: BlockMove,
):
    payload.position.validate_exclusive()

    page = resolve_page(page_id)
    require_edit_permission(request, page)
    require_if_match(request, page)

    field_name = body_field_name_for(page)
    body = serialize_body(resolve_page_for_read(page_id), field_name)
    idx, block = _find_block(body, block_uuid)

    # Remove the block, then resolve the insertion index in the shorter list.
    insert_at = _resolve_position(body, payload.position, exclude_uuid=block_uuid)
    new_body = [b for b in body if b.get("id") != block_uuid]
    new_body.insert(insert_at, block)

    etag = _commit_body(page, new_body, field_name, request, response)
    return {"moved_uuid": block_uuid, "_etag": etag}
