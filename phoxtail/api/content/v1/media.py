"""``/api/content/v1/media/`` — image + document endpoints.

The pages domain owns these because ``wagtailimages`` and ``wagtaildocs``
are required by every Wagtail install. FK lookups for app-specific
models (blog authors, etc.) live in the owning app instead.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Body, File, Form, Query, Router, UploadedFile

from phoxtail.api.content.v1.schemas import (
    DocumentList,
    ImageItem,
    ImageList,
    ImagePatch,
)

router = Router()


@router.get(
    "/images/",
    response={200: ImageList},
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
    items = [_serialize_image(img, request) for img in qs[offset : offset + limit]]
    return {"items": items, "total": total}


@router.get(
    "/images/{image_id}/",
    response={200: ImageItem, 404: dict},
    summary="Fetch a single image by ID",
)
def get_image(request: HttpRequest, image_id: int):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        return 404, {"detail": "Image not found"}

    return 200, _serialize_image(img, request)


@router.post(
    "/images/",
    response={201: ImageItem},
    summary="Upload a new image to the Wagtail library",
)
def upload_image(
    request: HttpRequest,
    title: str = Form(...),
    file: UploadedFile = File(...),
):
    from wagtail.images import get_image_model

    Image = get_image_model()
    img = Image(title=title, file=file)
    img.save()
    return 201, _serialize_image(img, request)


@router.get(
    "/images/{image_id}/view/",
    response=None,
    summary="Return a JPEG rendition of an image (max 1024×1024)",
)
def view_image(request: HttpRequest, image_id: int):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        return HttpResponse(status=404)

    rendition = img.get_rendition("max-1024x1024|format-jpeg")
    with rendition.file.open("rb") as f:
        return HttpResponse(f.read(), content_type="image/jpeg")


@router.patch(
    "/images/{image_id}/",
    response={200: ImageItem, 404: dict},
    summary="Update image metadata (description, tags, focal point)",
)
def update_image(request: HttpRequest, image_id: int, payload: ImagePatch = Body(...)):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        return 404, {"detail": "Image not found"}

    update_fields: list[str] = []
    if payload.title is not None:
        img.title = payload.title
        update_fields.append("title")
    if payload.description is not None:
        img.description = payload.description
        update_fields.append("description")
    if payload.focal_point is not None:
        img.focal_point_x = payload.focal_point.x
        img.focal_point_y = payload.focal_point.y
        img.focal_point_width = payload.focal_point.width
        img.focal_point_height = payload.focal_point.height
        update_fields.extend(
            [
                "focal_point_x",
                "focal_point_y",
                "focal_point_width",
                "focal_point_height",
            ]
        )
    if update_fields:
        img.save(update_fields=update_fields)
    if payload.tags is not None:
        img.tags.set(payload.tags)

    return 200, _serialize_image(img, request)


@router.get(
    "/documents/",
    response={200: DocumentList},
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
        {
            "id": doc.pk,
            "title": doc.title,
            "description": "",
            "tags": [],
            "focal_point": None,
            "file_url": _safe_url(doc, request),
        }
        for doc in qs[offset : offset + limit]
    ]
    return {"items": items, "total": total}


def _serialize_image(img, request: HttpRequest) -> dict:
    has_fp = (
        img.focal_point_x is not None
        and img.focal_point_y is not None
        and img.focal_point_width is not None
        and img.focal_point_height is not None
    )
    return {
        "id": img.pk,
        "title": img.title,
        "width": img.width,
        "height": img.height,
        "description": img.description or "",
        "tags": list(img.tags.names()),
        "focal_point": {
            "x": img.focal_point_x,
            "y": img.focal_point_y,
            "width": img.focal_point_width,
            "height": img.focal_point_height,
        }
        if has_fp
        else None,
        "file_url": _safe_url(img, request),
    }


def _safe_url(obj, request: HttpRequest | None = None) -> str | None:
    f = getattr(obj, "file", None)
    if not f:
        return None
    try:
        raw = f.url
    except (ValueError, AttributeError):
        return None
    if request is not None and raw.startswith("/"):
        return request.build_absolute_uri(raw)
    return raw
