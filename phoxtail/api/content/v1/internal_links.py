"""``/api/content/v1/internal-links`` — InternalLink endpoints."""

from __future__ import annotations

import hashlib

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.api.content.v1.schemas import (
    Error,
    InternalLinkCreate,
    InternalLinkItem,
    InternalLinkList,
    InternalLinkPatch,
)
from phoxtail.core.models import InternalLink

router = Router()


def _serialize(link: InternalLink) -> dict:
    return {
        "id": link.id,
        "uuid": str(link.uuid),
        "label": link.label,
        "url_name": link.url_name,
        "url": link.url,
        "created_at": link.created_at.isoformat(),
        "updated_at": link.updated_at.isoformat(),
    }


def _etag(link: InternalLink) -> str:
    h = hashlib.sha256()
    for part in (link.label, link.url_name, link.updated_at.isoformat()):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return f'W/"{h.hexdigest()[:16]}"'


def _resolve(pk: int) -> InternalLink:
    try:
        return InternalLink.objects.get(pk=pk)
    except InternalLink.DoesNotExist as exc:
        raise HttpError(404, f"InternalLink {pk} not found.") from exc


def _format_validation_error(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{k}: {', '.join(v)}" if isinstance(v, list) else f"{k}: {v}" for k, v in exc.message_dict.items()
        )
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)


@router.get("/", response={200: InternalLinkList}, summary="List InternalLinks")
def list_internal_links(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on label and url_name."),
):
    qs = InternalLink.objects.order_by("label")
    if search:
        qs = get_search_backend().autocomplete(search, qs)
    return {"items": [_serialize(link) for link in qs], "total": qs.count()}


@router.get(
    "/{link_id}/",
    response={200: InternalLinkItem, 404: Error},
    summary="Show an InternalLink by numeric ID",
)
def get_internal_link(request: HttpRequest, response: HttpResponse, link_id: int):
    link = _resolve(link_id)
    response["ETag"] = _etag(link)
    return _serialize(link)


@router.post(
    "/",
    response={201: InternalLinkItem, 400: Error, 409: Error},
    summary="Create an InternalLink",
)
def create_internal_link(request: HttpRequest, response: HttpResponse, payload: InternalLinkCreate):
    link = InternalLink(label=payload.label, url_name=payload.url_name)
    try:
        link.full_clean()
    except ValidationError as exc:
        raise HttpError(400, _format_validation_error(exc))
    try:
        link.save()
    except IntegrityError:
        raise HttpError(409, f"InternalLink with url_name '{payload.url_name}' already exists.")
    response["ETag"] = _etag(link)
    return 201, _serialize(link)


@router.patch(
    "/{link_id}/",
    response={200: InternalLinkItem, 400: Error, 404: Error, 412: Error, 428: Error},
    summary="Update an InternalLink by numeric ID",
)
def update_internal_link(
    request: HttpRequest,
    response: HttpResponse,
    link_id: int,
    payload: InternalLinkPatch,
):
    if_match = request.headers.get("If-Match")
    if not if_match:
        raise HttpError(
            428,
            "If-Match header is required. Send the ETag from your most recent GET of this internal link.",
        )

    link = _resolve(link_id)

    candidates = {t.strip() for t in if_match.split(",")}
    normalized = {t[2:] if t.startswith("W/") else t for t in candidates}
    current = _etag(link)
    current_norm = current[2:] if current.startswith("W/") else current
    if current_norm not in normalized and "*" not in candidates:
        raise HttpError(
            412,
            "ETag mismatch: the link has changed since you last read it. Re-fetch and retry.",
        )

    if payload.label is not None:
        link.label = payload.label
    if payload.url_name is not None:
        link.url_name = payload.url_name

    try:
        link.full_clean()
    except ValidationError as exc:
        raise HttpError(400, _format_validation_error(exc))

    link.save()
    response["ETag"] = _etag(link)
    return _serialize(link)


@router.delete(
    "/{link_id}/",
    response={204: None, 404: Error},
    summary="Delete an InternalLink by numeric ID",
)
def delete_internal_link(request: HttpRequest, link_id: int):
    link = _resolve(link_id)
    link.delete()
    return 204, None
