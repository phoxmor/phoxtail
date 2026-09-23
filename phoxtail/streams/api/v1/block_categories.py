"""``/api/streams/v1/block-categories`` — BlockCategory CRUD + block↔category assignment."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Schema
from ninja.errors import HttpError

from phoxtail.api.auth import guarded
from phoxtail.api.pagination import Router
from phoxtail.api.search import narrow_by_search
from phoxtail.streams.api.v1._helpers import (
    block_category_etag,
    etag_matches,
    resolve_block_by_pk,
    resolve_block_category_by_pk,
)
from phoxtail.streams.api.v1.schemas import (
    BlockCategoryCreate,
    BlockCategoryItem,
    BlockCategoryUpdate,
    Error,
)
from phoxtail.streams.models import BlockCategory

router = Router()
assignment_router = Router()


class _CategoryIdsPayload(Schema):
    category_ids: list[int]


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response={200: list[BlockCategoryItem]},
    summary="List BlockCategories",
    auth=guarded("phoxtail_streams.view_blockcategory"),
)
def list_block_categories(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on category name."),
):
    qs = BlockCategory.objects.order_by("sort_order", "name")
    if search:
        qs = narrow_by_search(qs, search)
    return qs


@router.post(
    "/",
    response={201: BlockCategoryItem, 400: Error, 409: Error},
    summary="Create a BlockCategory",
    auth=guarded("phoxtail_streams.add_blockcategory"),
)
def create_block_category(request: HttpRequest, response: HttpResponse, payload: BlockCategoryCreate):
    if BlockCategory.objects.filter(slug=payload.slug).exists():
        raise HttpError(409, f"A category with slug '{payload.slug}' already exists.")

    c = BlockCategory(name=payload.name, slug=payload.slug, description=payload.description)

    try:
        c.full_clean()
    except ValidationError as exc:
        raise HttpError(400, _format_validation_error(exc))

    c.save()
    response["ETag"] = block_category_etag(c)
    return 201, c


@router.get(
    "/{category_id}/",
    response={200: BlockCategoryItem, 404: Error},
    summary="Get a BlockCategory",
    auth=guarded("phoxtail_streams.view_blockcategory"),
)
def get_block_category(request: HttpRequest, response: HttpResponse, category_id: int):
    c = resolve_block_category_by_pk(category_id)
    response["ETag"] = block_category_etag(c)
    return c


@router.patch(
    "/{category_id}/",
    response={200: BlockCategoryItem, 400: Error, 404: Error, 409: Error, 412: Error, 428: Error},
    summary="Update a BlockCategory",
    auth=guarded("phoxtail_streams.change_blockcategory"),
)
def update_block_category(
    request: HttpRequest,
    response: HttpResponse,
    category_id: int,
    payload: BlockCategoryUpdate,
):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this category.",
        )

    c = resolve_block_category_by_pk(category_id)
    current = block_category_etag(c)

    if not etag_matches(if_match, current):
        raise HttpError(
            412,
            "ETag mismatch: the category has changed since you last read it. Re-fetch and retry.",
        )

    if payload.slug is not None:
        if BlockCategory.objects.filter(slug=payload.slug).exclude(pk=c.pk).exists():
            raise HttpError(409, f"A category with slug '{payload.slug}' already exists.")
        c.slug = payload.slug
    if payload.name is not None:
        c.name = payload.name
    if payload.description is not None:
        c.description = payload.description

    try:
        c.full_clean()
    except ValidationError as exc:
        raise HttpError(400, _format_validation_error(exc))

    c.save()
    response["ETag"] = block_category_etag(c)
    return c


@router.delete(
    "/{category_id}/",
    response={204: None, 404: Error},
    summary="Delete a BlockCategory",
    auth=guarded("phoxtail_streams.delete_blockcategory"),
)
def delete_block_category(request: HttpRequest, category_id: int):
    c = resolve_block_category_by_pk(category_id)
    c.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Block↔category assignment
# ---------------------------------------------------------------------------


@assignment_router.get(
    "/{block_id}/categories/",
    response={200: list[BlockCategoryItem], 404: Error},
    summary="List categories assigned to a block",
    auth=guarded("phoxtail_streams.view_block"),
)
def list_block_categories_for_block(request: HttpRequest, block_id: int):
    return resolve_block_by_pk(block_id).categories.order_by("sort_order", "name")


@assignment_router.put(
    "/{block_id}/categories/",
    response={200: list[BlockCategoryItem], 400: Error, 404: Error},
    summary="Replace the full category set for a block",
    auth=guarded("phoxtail_streams.change_block"),
)
def set_block_categories(request: HttpRequest, block_id: int, payload: _CategoryIdsPayload):
    b = resolve_block_by_pk(block_id)
    categories = []
    for cat_id in payload.category_ids:
        categories.append(resolve_block_category_by_pk(cat_id))
    b.categories.set(categories)
    # A write answers with the set it made, whole: it is not a page of it.
    return list(b.categories.order_by("sort_order", "name"))


@assignment_router.post(
    "/{block_id}/categories/{category_id}/",
    response={201: BlockCategoryItem, 404: Error, 409: Error},
    summary="Add one category to a block",
    auth=guarded("phoxtail_streams.change_block"),
)
def add_block_category(request: HttpRequest, response: HttpResponse, block_id: int, category_id: int):
    b = resolve_block_by_pk(block_id)
    c = resolve_block_category_by_pk(category_id)
    if b.categories.filter(pk=c.pk).exists():
        raise HttpError(409, f"Category {category_id} is already assigned to block {block_id}.")
    b.categories.add(c)
    return 201, c


@assignment_router.delete(
    "/{block_id}/categories/{category_id}/",
    response={204: None, 404: Error},
    summary="Remove one category from a block",
    auth=guarded("phoxtail_streams.change_block"),
)
def remove_block_category(request: HttpRequest, block_id: int, category_id: int):
    b = resolve_block_by_pk(block_id)
    c = resolve_block_category_by_pk(category_id)
    if not b.categories.filter(pk=c.pk).exists():
        raise HttpError(404, f"Category {category_id} is not assigned to block {block_id}.")
    b.categories.remove(c)
    return 204, None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_validation_error(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{k}: {', '.join(v)}" if isinstance(v, list) else f"{k}: {v}" for k, v in exc.message_dict.items()
        )
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
