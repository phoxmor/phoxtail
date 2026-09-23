"""``/api/streams/v1/collections`` — VariantCollection endpoints."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from ninja import Query
from ninja.errors import HttpError

from phoxtail.api.auth import guarded
from phoxtail.api.pagination import Router
from phoxtail.api.search import narrow_by_search
from phoxtail.streams.api.v1._helpers import (
    collection_etag,
    etag_matches,
    resolve_collection_by_pk,
)
from phoxtail.streams.api.v1.schemas import (
    Error,
    VariantCollectionCreate,
    VariantCollectionSummary,
    VariantCollectionUpdate,
)
from phoxtail.streams.models import VariantCollection

router = Router()


@router.get(
    "/",
    response={200: list[VariantCollectionSummary]},
    summary="List VariantCollections",
    auth=guarded("phoxtail_streams.view_variantcollection"),
)
def list_collections(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on collection name and identifier."),
):
    qs = VariantCollection.objects.annotate(variant_count=Count("variants", distinct=True)).order_by("name")
    if search:
        qs = narrow_by_search(qs, search)
    return qs


@router.get(
    "/{collection_id}/",
    response={200: VariantCollectionSummary, 404: Error},
    summary="Show a VariantCollection by numeric ID",
    auth=guarded("phoxtail_streams.view_variantcollection"),
)
def get_collection_by_id(request: HttpRequest, response: HttpResponse, collection_id: int):
    c = resolve_collection_by_pk(collection_id)
    response["ETag"] = collection_etag(c)
    return c


@router.patch(
    "/{collection_id}/",
    response={200: VariantCollectionSummary, 400: Error, 404: Error, 409: Error, 412: Error, 428: Error},
    summary="Update a VariantCollection by numeric ID",
    auth=guarded("phoxtail_streams.change_variantcollection"),
)
def update_collection_by_id(
    request: HttpRequest,
    response: HttpResponse,
    collection_id: int,
    payload: VariantCollectionUpdate,
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
    return c


@router.post(
    "/",
    response={201: VariantCollectionSummary, 400: Error, 409: Error},
    summary="Create a VariantCollection",
    auth=guarded("phoxtail_streams.add_variantcollection"),
)
def create_collection(request: HttpRequest, response: HttpResponse, payload: VariantCollectionCreate):
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
    return 201, c


@router.delete(
    "/{collection_id}/",
    response={204: None, 404: Error},
    summary="Delete a VariantCollection by numeric ID",
    auth=guarded("phoxtail_streams.delete_variantcollection"),
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
