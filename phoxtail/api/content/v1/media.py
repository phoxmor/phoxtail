"""``/api/content/v1/media/`` — image, document, video, and audio endpoints.

The pages domain owns these because ``wagtailimages``, ``wagtaildocs``, and
``wagtailmedia`` are required by every Phoxtail engine install. FK lookups
for app-specific models live in the owning app instead.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Body, File, Form, Query, Router, UploadedFile

from phoxtail.api.content.v1.schemas import (
    AudioItem,
    AudioList,
    AudioPatch,
    DocumentItem,
    DocumentList,
    DocumentPatch,
    ImageItem,
    ImageList,
    ImagePatch,
    VideoItem,
    VideoList,
    VideoPatch,
)

router = Router()


# ---------------------------------------------------------------------------
# Shared collection helper
# ---------------------------------------------------------------------------


def _resolve_collection_or_400(collection_id: int):
    from wagtail.models import Collection

    try:
        return Collection.objects.get(pk=collection_id)
    except Collection.DoesNotExist:
        from ninja.errors import HttpError

        raise HttpError(400, f"Collection {collection_id} not found.")


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


@router.get(
    "/images/",
    response={200: ImageList},
    summary="Search images by title",
)
def list_images(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from wagtail.images import get_image_model

    Image = get_image_model()
    qs = Image.objects.all().order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

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
    collection_id: int | None = Form(None),
):
    from wagtail.images import get_image_model

    Image = get_image_model()
    img = Image(title=title, file=file)
    if collection_id is not None:
        img.collection = _resolve_collection_or_400(collection_id)
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
    if payload.collection_id is not None:
        img.collection = _resolve_collection_or_400(payload.collection_id)
        update_fields.append("collection")
    if update_fields:
        img.save(update_fields=update_fields)
    if payload.tags is not None:
        img.tags.set(payload.tags)

    return 200, _serialize_image(img, request)


@router.delete(
    "/images/{image_id}/",
    response={204: None, 404: dict},
    summary="Delete an image from the Wagtail library",
)
def delete_image(request: HttpRequest, image_id: int):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        return 404, {"detail": "Image not found"}

    img.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.get(
    "/documents/",
    response={200: DocumentList},
    summary="Search documents by title",
)
def list_documents(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    qs = Document.objects.all().order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

    total = qs.count()
    items = [_serialize_document(doc, request) for doc in qs[offset : offset + limit]]
    return {"items": items, "total": total}


@router.get(
    "/documents/{document_id}/",
    response={200: DocumentItem, 404: dict},
    summary="Fetch a single document by ID",
)
def get_document(request: HttpRequest, document_id: int):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return 404, {"detail": "Document not found"}

    return 200, _serialize_document(doc, request)


@router.post(
    "/documents/",
    response={201: DocumentItem},
    summary="Upload a new document to the Wagtail library",
)
def upload_document(
    request: HttpRequest,
    title: str = Form(...),
    file: UploadedFile = File(...),
    description: str = Form(""),
    collection_id: int | None = Form(None),
):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    doc = Document(title=title, file=file)
    if description:
        doc.description = description
    if collection_id is not None:
        doc.collection = _resolve_collection_or_400(collection_id)
    doc.save()
    doc.get_file_size()
    return 201, _serialize_document(doc, request)


@router.patch(
    "/documents/{document_id}/",
    response={200: DocumentItem, 404: dict},
    summary="Update document metadata (title, tags)",
)
def update_document(
    request: HttpRequest, document_id: int, payload: DocumentPatch = Body(...)
):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return 404, {"detail": "Document not found"}

    doc_update_fields: list[str] = []
    if payload.title is not None:
        doc.title = payload.title
        doc_update_fields.append("title")
    if payload.description is not None:
        doc.description = payload.description
        doc_update_fields.append("description")
    if payload.collection_id is not None:
        doc.collection = _resolve_collection_or_400(payload.collection_id)
        doc_update_fields.append("collection")
    if doc_update_fields:
        doc.save(update_fields=doc_update_fields)
    if payload.tags is not None:
        doc.tags.set(payload.tags)

    return 200, _serialize_document(doc, request)


@router.delete(
    "/documents/{document_id}/",
    response={204: None, 404: dict},
    summary="Delete a document from the Wagtail library",
)
def delete_document(request: HttpRequest, document_id: int):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return 404, {"detail": "Document not found"}

    doc.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------


@router.get(
    "/videos/",
    response={200: VideoList},
    summary="Search videos by title",
)
def list_videos(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    qs = Media.objects.filter(type="video").order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

    total = qs.count()
    items = [_serialize_video(m, request) for m in qs[offset : offset + limit]]
    return {"items": items, "total": total}


@router.get(
    "/videos/{video_id}/",
    response={200: VideoItem, 404: dict},
    summary="Fetch a single video by ID",
)
def get_video(request: HttpRequest, video_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=video_id, type="video")
    except Media.DoesNotExist:
        return 404, {"detail": "Video not found"}

    return 200, _serialize_video(m, request)


@router.post(
    "/videos/",
    response={201: VideoItem},
    summary="Upload a new video to the Wagtail media library",
)
def upload_video(
    request: HttpRequest,
    title: str = Form(...),
    file: UploadedFile = File(...),
    description: str = Form(""),
    duration: float = Form(0.0),
    width: int | None = Form(None),
    height: int | None = Form(None),
    collection_id: int | None = Form(None),
):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    m = Media(
        title=title,
        file=file,
        type="video",
        duration=duration,
        width=width,
        height=height,
    )
    if description:
        m.description = description
    if collection_id is not None:
        m.collection = _resolve_collection_or_400(collection_id)
    m.save()
    return 201, _serialize_video(m, request)


@router.patch(
    "/videos/{video_id}/",
    response={200: VideoItem, 404: dict},
    summary="Update video metadata (title, tags, duration, dimensions)",
)
def update_video(request: HttpRequest, video_id: int, payload: VideoPatch = Body(...)):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=video_id, type="video")
    except Media.DoesNotExist:
        return 404, {"detail": "Video not found"}

    update_fields: list[str] = []
    for field in ("title", "description", "duration", "width", "height"):
        val = getattr(payload, field)
        if val is not None:
            setattr(m, field, val)
            update_fields.append(field)
    if payload.collection_id is not None:
        m.collection = _resolve_collection_or_400(payload.collection_id)
        update_fields.append("collection")
    if update_fields:
        m.save(update_fields=update_fields)
    if payload.tags is not None:
        m.tags.set(payload.tags)

    return 200, _serialize_video(m, request)


@router.delete(
    "/videos/{video_id}/",
    response={204: None, 404: dict},
    summary="Delete a video from the Wagtail media library",
)
def delete_video(request: HttpRequest, video_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=video_id, type="video")
    except Media.DoesNotExist:
        return 404, {"detail": "Video not found"}

    m.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


@router.get(
    "/audio/",
    response={200: AudioList},
    summary="Search audio files by title",
)
def list_audio(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    qs = Media.objects.filter(type="audio").order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

    total = qs.count()
    items = [_serialize_audio(m, request) for m in qs[offset : offset + limit]]
    return {"items": items, "total": total}


@router.get(
    "/audio/{audio_id}/",
    response={200: AudioItem, 404: dict},
    summary="Fetch a single audio file by ID",
)
def get_audio(request: HttpRequest, audio_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=audio_id, type="audio")
    except Media.DoesNotExist:
        return 404, {"detail": "Audio not found"}

    return 200, _serialize_audio(m, request)


@router.post(
    "/audio/",
    response={201: AudioItem},
    summary="Upload a new audio file to the Wagtail media library",
)
def upload_audio(
    request: HttpRequest,
    title: str = Form(...),
    file: UploadedFile = File(...),
    description: str = Form(""),
    duration: float = Form(0.0),
    collection_id: int | None = Form(None),
):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    m = Media(title=title, file=file, type="audio", duration=duration)
    if description:
        m.description = description
    if collection_id is not None:
        m.collection = _resolve_collection_or_400(collection_id)
    m.save()
    return 201, _serialize_audio(m, request)


@router.patch(
    "/audio/{audio_id}/",
    response={200: AudioItem, 404: dict},
    summary="Update audio metadata (title, tags, duration)",
)
def update_audio(request: HttpRequest, audio_id: int, payload: AudioPatch = Body(...)):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=audio_id, type="audio")
    except Media.DoesNotExist:
        return 404, {"detail": "Audio not found"}

    update_fields: list[str] = []
    for field in ("title", "description", "duration"):
        val = getattr(payload, field)
        if val is not None:
            setattr(m, field, val)
            update_fields.append(field)
    if payload.collection_id is not None:
        m.collection = _resolve_collection_or_400(payload.collection_id)
        update_fields.append("collection")
    if update_fields:
        m.save(update_fields=update_fields)
    if payload.tags is not None:
        m.tags.set(payload.tags)

    return 200, _serialize_audio(m, request)


@router.delete(
    "/audio/{audio_id}/",
    response={204: None, 404: dict},
    summary="Delete an audio file from the Wagtail media library",
)
def delete_audio(request: HttpRequest, audio_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=audio_id, type="audio")
    except Media.DoesNotExist:
        return 404, {"detail": "Audio not found"}

    m.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


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
        "collection_id": img.collection_id,
    }


def _serialize_document(doc, request: HttpRequest) -> dict:
    return {
        "id": doc.pk,
        "title": doc.title,
        "description": getattr(doc, "description", "") or "",
        "tags": list(doc.tags.names()),
        "file_size": doc.file_size,
        "filename": doc.filename,
        "file_extension": doc.file_extension,
        "file_url": _safe_url(doc, request),
        "collection_id": doc.collection_id,
    }


def _serialize_video(m, request: HttpRequest) -> dict:
    return {
        "id": m.pk,
        "title": m.title,
        "description": getattr(m, "description", "") or "",
        "duration": m.duration,
        "width": m.width,
        "height": m.height,
        "tags": list(m.tags.names()),
        "file_url": _safe_url(m, request),
        "thumbnail_url": _safe_url_field(m, "thumbnail", request),
        "collection_id": m.collection_id,
    }


def _serialize_audio(m, request: HttpRequest) -> dict:
    return {
        "id": m.pk,
        "title": m.title,
        "description": getattr(m, "description", "") or "",
        "duration": m.duration,
        "tags": list(m.tags.names()),
        "file_url": _safe_url(m, request),
        "collection_id": m.collection_id,
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


def _safe_url_field(
    obj, field_name: str, request: HttpRequest | None = None
) -> str | None:
    f = getattr(obj, field_name, None)
    if not f:
        return None
    try:
        raw = f.url
    except (ValueError, AttributeError):
        return None
    if request is not None and raw.startswith("/"):
        return request.build_absolute_uri(raw)
    return raw
