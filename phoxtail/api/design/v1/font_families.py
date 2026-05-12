"""``/api/design/v1/font-families/`` — FontFamily CRUD."""

from __future__ import annotations

from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.design.v1._helpers import (
    font_family_etag,
    font_family_summary,
    require_if_match,
    resolve_font_family,
)

router = Router()

_CATEGORY_CHOICES = ["serif", "sans-serif", "monospace", "display", "handwriting"]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FontFamilySummary(Schema):
    id: int
    name: str
    description: str
    category: str
    fallback: str
    weight_count: int
    created_at: str | None
    updated_at: str


class FontFamilyList(Schema):
    font_families: list[FontFamilySummary]
    total: int


class FontFamilyCreate(Schema):
    name: str
    description: str = ""
    category: str = "sans-serif"
    fallback: str = "system-ui, -apple-system, sans-serif"


class FontFamilyPatch(Schema):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    fallback: str | None = None


class Error(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response={200: FontFamilyList}, summary="List font families")
def list_font_families(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on font name."),
    category: str | None = Query(None, description="Filter by category."),
):
    from phoxtail.design.models import FontFamily

    qs = FontFamily.objects.annotate(_weight_count=Count("weights")).order_by("name")
    if category:
        qs = qs.filter(category=category)
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    items = [font_family_summary(ff) for ff in qs]
    return {"font_families": items, "total": len(items)}


@router.post(
    "/",
    response={201: FontFamilySummary, 400: Error, 409: Error},
    summary="Create a font family",
)
def create_font_family(
    request: HttpRequest, response: HttpResponse, payload: FontFamilyCreate
):
    from phoxtail.design.models import FontFamily

    if payload.category not in _CATEGORY_CHOICES:
        raise HttpError(400, f"Invalid category. Choices: {_CATEGORY_CHOICES}")

    try:
        ff = FontFamily.objects.create(
            name=payload.name,
            description=payload.description,
            category=payload.category,
            fallback=payload.fallback,
        )
    except IntegrityError:
        raise HttpError(409, f"A font family named '{payload.name}' already exists.")

    response["ETag"] = font_family_etag(ff)
    return 201, font_family_summary(ff)


@router.get(
    "/{font_id}/",
    response={200: FontFamilySummary, 404: Error},
    summary="Get a font family",
)
def get_font_family(request: HttpRequest, response: HttpResponse, font_id: int):
    ff = resolve_font_family(font_id)
    response["ETag"] = font_family_etag(ff)
    return font_family_summary(ff)


@router.patch(
    "/{font_id}/",
    response={
        200: FontFamilySummary,
        400: Error,
        404: Error,
        409: Error,
        412: Error,
        428: Error,
    },
    summary="Update a font family",
)
def patch_font_family(
    request: HttpRequest,
    response: HttpResponse,
    font_id: int,
    payload: FontFamilyPatch,
):
    ff = resolve_font_family(font_id)
    require_if_match(request, font_family_etag(ff))

    data = payload.model_dump(exclude_unset=True)
    if "category" in data and data["category"] not in _CATEGORY_CHOICES:
        raise HttpError(400, f"Invalid category. Choices: {_CATEGORY_CHOICES}")

    for field, value in data.items():
        setattr(ff, field, value)
    try:
        ff.save()
    except IntegrityError:
        raise HttpError(409, "A font family with that name already exists.")

    ff.refresh_from_db()
    response["ETag"] = font_family_etag(ff)
    return font_family_summary(ff)


@router.delete(
    "/{font_id}/",
    response={204: None, 404: Error, 412: Error, 428: Error},
    summary="Delete a font family",
)
def delete_font_family(request: HttpRequest, font_id: int):
    ff = resolve_font_family(font_id)
    require_if_match(request, font_family_etag(ff))
    ff.delete()
    return 204, None
