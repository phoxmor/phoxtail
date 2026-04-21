"""``/api/pages/v1/media/`` — image + document lookup endpoints.

Read-only. The pages domain owns these because ``wagtailimages`` and
``wagtaildocs`` are required by every Wagtail install — they are not
optional apps. FK lookups for app-specific models (blog authors, etc.)
live in the owning app instead.
"""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Query, Router

from phoxtail.api.pages.v1.schemas import MediaList

router = Router()


@router.get(
    "/images/",
    response={200: MediaList},
    summary="Search images by title",
)
def list_images(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from wagtail.images import get_image_model

    Image = get_image_model()
    qs = Image.objects.all().order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)

    total = qs.count()
    items = [
        {"id": img.pk, "title": img.title, "file_url": _safe_url(img)}
        for img in qs[offset : offset + limit]
    ]
    return {"items": items, "total": total}


@router.get(
    "/documents/",
    response={200: MediaList},
    summary="Search documents by title",
)
def list_documents(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    qs = Document.objects.all().order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)

    total = qs.count()
    items = [
        {"id": doc.pk, "title": doc.title, "file_url": _safe_url(doc)}
        for doc in qs[offset : offset + limit]
    ]
    return {"items": items, "total": total}


def _safe_url(obj) -> str | None:
    f = getattr(obj, "file", None)
    if not f:
        return None
    try:
        return f.url
    except (ValueError, AttributeError):
        return None
