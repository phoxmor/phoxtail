"""``/api/streams/v1/block-categories`` — BlockCategory CRUD + block↔category assignment."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.streams.api.v1._helpers import (
    block_category_detail,
    block_category_etag,
    etag_matches,
    resolve_block_by_pk,
    resolve_block_category_by_pk,
)
from phoxtail.streams.api.v1.schemas import (
    BlockCategoryCreate,
    BlockCategoryItem,
    BlockCategoryList,
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


@router.get("/", response={200: BlockCategoryList}, summary="List BlockCategories")
def list_block_categories(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on category name."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    qs = BlockCategory.objects.order_by("sort_order", "name")
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    items = [block_category_detail(c) for c in qs[offset : offset + limit]]
    return {"items": items, "total": qs.count()}


@router.post(
    "/",
    response={201: BlockCategoryItem, 400: Error, 409: Error},
    summary="Create a BlockCategory",
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
    return 201, block_category_detail(c)


@router.get(
    "/{category_id}/",
    response={200: BlockCategoryItem, 404: Error},
    summary="Get a BlockCategory",
)
def get_block_category(request: HttpRequest, response: HttpResponse, category_id: int):
    c = resolve_block_category_by_pk(category_id)
    response["ETag"] = block_category_etag(c)
    return block_category_detail(c)


@router.patch(
    "/{category_id}/",
    response={200: BlockCategoryItem, 400: Error, 404: Error, 409: Error, 412: Error, 428: Error},
    summary="Update a BlockCategory",
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
    return block_category_detail(c)


@router.delete(
    "/{category_id}/",
    response={204: None, 404: Error},
    summary="Delete a BlockCategory",
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
    response={200: BlockCategoryList, 404: Error},
    summary="List categories assigned to a block",
)
def list_block_categories_for_block(request: HttpRequest, block_id: int):
    b = resolve_block_by_pk(block_id)
    items = [block_category_detail(c) for c in b.categories.order_by("sort_order", "name")]
    return {"items": items, "total": len(items)}


@assignment_router.put(
    "/{block_id}/categories/",
    response={200: BlockCategoryList, 400: Error, 404: Error},
    summary="Replace the full category set for a block",
)
def set_block_categories(request: HttpRequest, block_id: int, payload: _CategoryIdsPayload):
    b = resolve_block_by_pk(block_id)
    categories = []
    for cat_id in payload.category_ids:
        categories.append(resolve_block_category_by_pk(cat_id))
    b.categories.set(categories)
    items = [block_category_detail(c) for c in b.categories.order_by("sort_order", "name")]
    return {"items": items, "total": len(items)}


@assignment_router.post(
    "/{block_id}/categories/{category_id}/",
    response={201: BlockCategoryItem, 404: Error, 409: Error},
    summary="Add one category to a block",
)
def add_block_category(request: HttpRequest, response: HttpResponse, block_id: int, category_id: int):
    b = resolve_block_by_pk(block_id)
    c = resolve_block_category_by_pk(category_id)
    if b.categories.filter(pk=c.pk).exists():
        raise HttpError(409, f"Category {category_id} is already assigned to block {block_id}.")
    b.categories.add(c)
    return 201, block_category_detail(c)


@assignment_router.delete(
    "/{block_id}/categories/{category_id}/",
    response={204: None, 404: Error},
    summary="Remove one category from a block",
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
