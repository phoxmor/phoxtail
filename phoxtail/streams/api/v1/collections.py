"""``/api/streams/v1/collections`` — VariantCollection endpoints."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.streams.api.v1._helpers import (
    collection_detail,
    collection_etag,
    collection_summary,
    etag_matches,
    resolve_collection_by_pk,
)
from phoxtail.streams.api.v1.schemas import (
    CollectionCreate,
    CollectionList,
    CollectionSummary,
    CollectionUpdate,
    Error,
)
from phoxtail.streams.models import VariantCollection

router = Router()


@router.get("/", response={200: CollectionList}, summary="List VariantCollections")
def list_collections(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on collection name and identifier."),
):
    qs = VariantCollection.objects.annotate(_variant_count=Count("variants", distinct=True)).order_by("name")
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    collections = [collection_summary(c, c._variant_count) for c in qs]
    return {"collections": collections, "total": len(collections)}


@router.get(
    "/{collection_id}/",
    response={200: CollectionSummary, 404: Error},
    summary="Show a VariantCollection by numeric ID",
)
def get_collection_by_id(request: HttpRequest, response: HttpResponse, collection_id: int):
    c = resolve_collection_by_pk(collection_id)
    response["ETag"] = collection_etag(c)
    return collection_detail(c, c.variants.count())


@router.patch(
    "/{collection_id}/",
    response={200: CollectionSummary, 400: Error, 404: Error, 409: Error, 412: Error, 428: Error},
    summary="Update a VariantCollection by numeric ID",
)
def update_collection_by_id(
    request: HttpRequest,
    response: HttpResponse,
    collection_id: int,
    payload: CollectionUpdate,
):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this collection.",
        )

    c = resolve_collection_by_pk(collection_id)
    current = collection_etag(c)

    if not etag_matches(if_match, current):
        raise HttpError(
            412,
            "ETag mismatch: the collection has changed since you last read it. Re-fetch and retry.",
        )

    if payload.identifier is not None:
        if VariantCollection.objects.filter(identifier=payload.identifier).exclude(pk=c.pk).exists():
            raise HttpError(409, f"A collection with identifier '{payload.identifier}' already exists.")
        c.identifier = payload.identifier
    if payload.name is not None:
        if VariantCollection.objects.filter(name=payload.name).exclude(pk=c.pk).exists():
            raise HttpError(409, f"A collection with name '{payload.name}' already exists.")
        c.name = payload.name
    if payload.description is not None:
        c.description = payload.description

    try:
        c.full_clean()
    except ValidationError as exc:
        detail = _format_validation_error(exc)
        raise HttpError(400, detail)

    c.save()

    response["ETag"] = collection_etag(c)
    return collection_detail(c, c.variants.count())


@router.post(
    "/",
    response={201: CollectionSummary, 400: Error, 409: Error},
    summary="Create a VariantCollection",
)
def create_collection(request: HttpRequest, response: HttpResponse, payload: CollectionCreate):
    if VariantCollection.objects.filter(Q(identifier=payload.identifier) | Q(name=payload.name)).exists():
        raise HttpError(409, "A collection with this identifier or name already exists.")

    c = VariantCollection(
        identifier=payload.identifier,
        name=payload.name,
        description=payload.description,
    )

    try:
        c.full_clean()
    except ValidationError as exc:
        detail = _format_validation_error(exc)
        raise HttpError(400, detail)

    try:
        c.save()
    except IntegrityError:
        raise HttpError(409, "A collection with this identifier or name already exists.")

    response["ETag"] = collection_etag(c)
    return 201, collection_detail(c, 0)


@router.delete(
    "/{collection_id}/",
    response={204: None, 404: Error},
    summary="Delete a VariantCollection by numeric ID",
)
def delete_collection(request: HttpRequest, collection_id: int):
    c = resolve_collection_by_pk(collection_id)
    c.delete()
    return 204, None


def _format_validation_error(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{k}: {', '.join(v)}" if isinstance(v, list) else f"{k}: {v}" for k, v in exc.message_dict.items()
        )
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
