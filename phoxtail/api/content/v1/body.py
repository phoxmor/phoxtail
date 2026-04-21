"""``/api/content/v1/pages/{id}/body/`` — StreamField body endpoints.

MVP shape: read the body + replace it wholesale. Surgical per-block
tools come later.
"""

from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from ninja import Router

from phoxtail.api.content.v1._helpers import (
    body_field_name_for,
    page_etag,
    replace_body,
    require_edit_permission,
    require_if_match,
    resolve_page,
    resolve_page_for_read,
    serialize_body,
)
from phoxtail.api.content.v1.schemas import BodyReplace, BodyResponse, Error

router = Router()


@router.get(
    "/{page_id}/body/",
    response={200: BodyResponse, 404: Error},
    summary="Get a page's StreamField body",
)
def get_body(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
):
    live = resolve_page(page_id)
    response["ETag"] = page_etag(live)
    draft = resolve_page_for_read(page_id)
    return {"body": serialize_body(draft, body_field_name_for(draft))}


@router.put(
    "/{page_id}/body/",
    response={
        200: BodyResponse,
        400: Error,
        403: Error,
        404: Error,
        412: Error,
        428: Error,
    },
    summary="Replace a page's body wholesale (creates a draft revision)",
)
def put_body(
    request: HttpRequest,
    response: HttpResponse,
    page_id: int,
    payload: BodyReplace,
):
    page = resolve_page(page_id)
    require_edit_permission(request, page)
    require_if_match(request, page)

    field_name = body_field_name_for(page)
    with transaction.atomic():
        replace_body(page, payload.body, field_name)
        # save_revision() saves the full in-memory state as a draft.
        # We do NOT call page.save() — that would make the new body live
        # immediately, bypassing the Wagtail revision/publish workflow.
        page.save_revision(user=request.auth)

    response["ETag"] = page_etag(page)
    return {"body": serialize_body(page, field_name)}
