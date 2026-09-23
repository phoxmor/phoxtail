"""``/api/media/v1/`` — image, document, video, and audio endpoints.

The pages domain owns these because ``wagtailimages``, ``wagtaildocs``, and
``wagtailmedia`` are required by every Phoxtail engine install. FK lookups
for app-specific models live in the owning app instead.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Body, File, Form, Query, UploadedFile

from phoxtail.api.auth import scoped
from phoxtail.api.pagination import Router
from phoxtail.media.api.v1._permissions import (
    DOCUMENT_CHOOSE,
    IMAGE_CHOOSE,
    MEDIA_CHOOSE,
    choosable,
    document_policy,
    image_policy,
    media_policy,
    require_collection,
    require_instance,
)
from phoxtail.media.api.v1.schemas import (
    AudioItem,
    AudioPatch,
    DocumentItem,
    DocumentPatch,
    ImageItem,
    ImagePatch,
    VideoItem,
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


def _upload_collection(collection_id: int | None):
    """The collection an upload lands in, named rather than left implicit.

    Wagtail's ``CollectionMember.collection`` field defaults to the root
    collection. That default has to be resolved *here* rather than left to
    ``save()``, because permission to add is asked of a collection and there
    is no answering it while the collection is still None.

    The default itself is read from Wagtail — ``get_root_collection_id`` is
    the callable the field is declared with — so the API cannot drift from
    where the admin would have put the same upload.
    """
    from wagtail.models import Collection
    from wagtail.models.media import get_root_collection_id

    if collection_id is None:
        return Collection.objects.get(pk=get_root_collection_id())
    return _resolve_collection_or_400(collection_id)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


@router.get(
    "/images/",
    response={200: list[ImageItem]},
    summary="Search images by title",
    auth=scoped("wagtailimages.choose_image"),
)
def list_images(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
):
    qs = choosable(image_policy(), request.auth.user, IMAGE_CHOOSE).order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

    return qs.prefetch_related("tags")


@router.get(
    "/images/{image_id}/",
    response={200: ImageItem, 404: dict},
    summary="Fetch a single image by ID",
    auth=scoped("wagtailimages.choose_image"),
)
def get_image(request: HttpRequest, image_id: int):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = choosable(image_policy(), request.auth.user, IMAGE_CHOOSE).get(pk=image_id)
    except Image.DoesNotExist:
        return 404, {"detail": "Image not found"}

    return 200, img


@router.post(
    "/images/",
    response={201: ImageItem},
    summary="Upload a new image to the Wagtail library",
    auth=scoped("wagtailimages.add_image"),
)
def upload_image(
    request: HttpRequest,
    title: str = Form(...),
    file: UploadedFile = File(...),
    collection_id: int | None = Form(None),
):
    from wagtail.images import get_image_model

    Image = get_image_model()
    collection = _upload_collection(collection_id)
    require_collection(image_policy(), request.auth.user, collection)

    img = Image(title=title, file=file, collection=collection)
    img.save()
    return 201, img


@router.get(
    "/images/{image_id}/view/",
    response=None,
    summary="Return a JPEG rendition of an image (max 1024×1024)",
    auth=scoped("wagtailimages.change_image"),
)
def view_image(request: HttpRequest, image_id: int):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        return HttpResponse(status=404)

    # ``wagtail.images.views.images.preview`` asks "change" before handing
    # back the bytes of one image, where the chooser asks "choose" for its
    # metadata. Serving the file is the heavier act, and this follows it.
    require_instance(image_policy(), request.auth.user, "change", img)

    # ``preserve-svg`` is Wagtail's own answer to a raster directive meeting a
    # vector file: it drops the rasterising operations for SVGs and leaves
    # them alone for everything else. Without it this raised
    # InvalidFilterSpecError and the endpoint answered 500 for every SVG in
    # the library — which is most logos.
    rendition = img.get_rendition("max-1024x1024|format-jpeg|preserve-svg")
    content_type = "image/svg+xml" if img.is_svg() else "image/jpeg"
    with rendition.file.open("rb") as f:
        return HttpResponse(f.read(), content_type=content_type)


@router.patch(
    "/images/{image_id}/",
    response={200: ImageItem, 404: dict},
    summary="Update image metadata (description, tags, focal point)",
    auth=scoped("wagtailimages.change_image"),
)
def update_image(request: HttpRequest, image_id: int, payload: ImagePatch = Body(...)):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        return 404, {"detail": "Image not found"}

    policy = image_policy()
    require_instance(policy, request.auth.user, "change", img)

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
        # Moving a file is adding it somewhere, so the destination is asked
        # its own question. Otherwise change-here would imply add-anywhere.
        destination = _resolve_collection_or_400(payload.collection_id)
        require_collection(policy, request.auth.user, destination)
        img.collection = destination
        update_fields.append("collection")
    if update_fields:
        img.save(update_fields=update_fields)
    if payload.tags is not None:
        img.tags.set(payload.tags)

    return 200, img


@router.delete(
    "/images/{image_id}/",
    response={204: None, 404: dict},
    summary="Delete an image from the Wagtail library",
    auth=scoped("wagtailimages.delete_image"),
)
def delete_image(request: HttpRequest, image_id: int):
    from wagtail.images import get_image_model

    Image = get_image_model()
    try:
        img = Image.objects.get(pk=image_id)
    except Image.DoesNotExist:
        return 404, {"detail": "Image not found"}

    require_instance(image_policy(), request.auth.user, "delete", img)
    img.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.get(
    "/documents/",
    response={200: list[DocumentItem]},
    summary="Search documents by title",
    auth=scoped("wagtaildocs.choose_document"),
)
def list_documents(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
):
    qs = choosable(document_policy(), request.auth.user, DOCUMENT_CHOOSE).order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

    return qs.prefetch_related("tags")


@router.get(
    "/documents/{document_id}/",
    response={200: DocumentItem, 404: dict},
    summary="Fetch a single document by ID",
    auth=scoped("wagtaildocs.choose_document"),
)
def get_document(request: HttpRequest, document_id: int):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    try:
        doc = choosable(document_policy(), request.auth.user, DOCUMENT_CHOOSE).get(pk=document_id)
    except Document.DoesNotExist:
        return 404, {"detail": "Document not found"}

    return 200, doc


@router.post(
    "/documents/",
    response={201: DocumentItem},
    summary="Upload a new document to the Wagtail library",
    auth=scoped("wagtaildocs.add_document"),
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
    collection = _upload_collection(collection_id)
    require_collection(document_policy(), request.auth.user, collection)

    doc = Document(title=title, file=file, collection=collection)
    if description:
        doc.description = description
    doc.save()
    doc.get_file_size()
    return 201, doc


@router.patch(
    "/documents/{document_id}/",
    response={200: DocumentItem, 404: dict},
    summary="Update document metadata (title, tags)",
    auth=scoped("wagtaildocs.change_document"),
)
def update_document(request: HttpRequest, document_id: int, payload: DocumentPatch = Body(...)):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return 404, {"detail": "Document not found"}

    policy = document_policy()
    require_instance(policy, request.auth.user, "change", doc)

    doc_update_fields: list[str] = []
    if payload.title is not None:
        doc.title = payload.title
        doc_update_fields.append("title")
    if payload.description is not None:
        doc.description = payload.description
        doc_update_fields.append("description")
    if payload.collection_id is not None:
        destination = _resolve_collection_or_400(payload.collection_id)
        require_collection(policy, request.auth.user, destination)
        doc.collection = destination
        doc_update_fields.append("collection")
    if doc_update_fields:
        doc.save(update_fields=doc_update_fields)
    if payload.tags is not None:
        doc.tags.set(payload.tags)

    return 200, doc


@router.delete(
    "/documents/{document_id}/",
    response={204: None, 404: dict},
    summary="Delete a document from the Wagtail library",
    auth=scoped("wagtaildocs.delete_document"),
)
def delete_document(request: HttpRequest, document_id: int):
    from wagtail.documents import get_document_model

    Document = get_document_model()
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return 404, {"detail": "Document not found"}

    require_instance(document_policy(), request.auth.user, "delete", doc)
    doc.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------


@router.get(
    "/videos/",
    response={200: list[VideoItem]},
    summary="Search videos by title",
    auth=scoped("wagtailmedia.change_media"),
)
def list_videos(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
):
    qs = choosable(media_policy(), request.auth.user, MEDIA_CHOOSE).filter(type="video").order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

    return qs.prefetch_related("tags")


@router.get(
    "/videos/{video_id}/",
    response={200: VideoItem, 404: dict},
    summary="Fetch a single video by ID",
    auth=scoped("wagtailmedia.change_media"),
)
def get_video(request: HttpRequest, video_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = choosable(media_policy(), request.auth.user, MEDIA_CHOOSE).get(pk=video_id, type="video")
    except Media.DoesNotExist:
        return 404, {"detail": "Video not found"}

    return 200, m


@router.post(
    "/videos/",
    response={201: VideoItem},
    summary="Upload a new video to the Wagtail media library",
    auth=scoped("wagtailmedia.add_media"),
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
    collection = _upload_collection(collection_id)
    require_collection(media_policy(), request.auth.user, collection)

    m = Media(
        title=title,
        file=file,
        type="video",
        duration=duration,
        width=width,
        height=height,
        collection=collection,
    )
    if description:
        m.description = description
    m.save()
    return 201, m


@router.patch(
    "/videos/{video_id}/",
    response={200: VideoItem, 404: dict},
    summary="Update video metadata (title, tags, duration, dimensions)",
    auth=scoped("wagtailmedia.change_media"),
)
def update_video(request: HttpRequest, video_id: int, payload: VideoPatch = Body(...)):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=video_id, type="video")
    except Media.DoesNotExist:
        return 404, {"detail": "Video not found"}

    policy = media_policy()
    require_instance(policy, request.auth.user, "change", m)

    update_fields: list[str] = []
    for field in ("title", "description", "duration", "width", "height"):
        val = getattr(payload, field)
        if val is not None:
            setattr(m, field, val)
            update_fields.append(field)
    if payload.collection_id is not None:
        destination = _resolve_collection_or_400(payload.collection_id)
        require_collection(policy, request.auth.user, destination)
        m.collection = destination
        update_fields.append("collection")
    if update_fields:
        m.save(update_fields=update_fields)
    if payload.tags is not None:
        m.tags.set(payload.tags)

    return 200, m


@router.delete(
    "/videos/{video_id}/",
    response={204: None, 404: dict},
    summary="Delete a video from the Wagtail media library",
    auth=scoped("wagtailmedia.delete_media"),
)
def delete_video(request: HttpRequest, video_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=video_id, type="video")
    except Media.DoesNotExist:
        return 404, {"detail": "Video not found"}

    require_instance(media_policy(), request.auth.user, "delete", m)
    m.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


@router.get(
    "/audio/",
    response={200: list[AudioItem]},
    summary="Search audio files by title",
    auth=scoped("wagtailmedia.change_media"),
)
def list_audio(
    request: HttpRequest,
    search: str | None = Query(None, description="Substring match on title."),
    collection: int | None = Query(None, description="Filter by collection id."),
):
    qs = choosable(media_policy(), request.auth.user, MEDIA_CHOOSE).filter(type="audio").order_by("-created_at")
    if search:
        qs = qs.filter(title__icontains=search)
    if collection is not None:
        qs = qs.filter(collection_id=collection)

    return qs.prefetch_related("tags")


@router.get(
    "/audio/{audio_id}/",
    response={200: AudioItem, 404: dict},
    summary="Fetch a single audio file by ID",
    auth=scoped("wagtailmedia.change_media"),
)
def get_audio(request: HttpRequest, audio_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = choosable(media_policy(), request.auth.user, MEDIA_CHOOSE).get(pk=audio_id, type="audio")
    except Media.DoesNotExist:
        return 404, {"detail": "Audio not found"}

    return 200, m


@router.post(
    "/audio/",
    response={201: AudioItem},
    summary="Upload a new audio file to the Wagtail media library",
    auth=scoped("wagtailmedia.add_media"),
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
    collection = _upload_collection(collection_id)
    require_collection(media_policy(), request.auth.user, collection)

    m = Media(title=title, file=file, type="audio", duration=duration, collection=collection)
    if description:
        m.description = description
    m.save()
    return 201, m


@router.patch(
    "/audio/{audio_id}/",
    response={200: AudioItem, 404: dict},
    summary="Update audio metadata (title, tags, duration)",
    auth=scoped("wagtailmedia.change_media"),
)
def update_audio(request: HttpRequest, audio_id: int, payload: AudioPatch = Body(...)):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=audio_id, type="audio")
    except Media.DoesNotExist:
        return 404, {"detail": "Audio not found"}

    policy = media_policy()
    require_instance(policy, request.auth.user, "change", m)

    update_fields: list[str] = []
    for field in ("title", "description", "duration"):
        val = getattr(payload, field)
        if val is not None:
            setattr(m, field, val)
            update_fields.append(field)
    if payload.collection_id is not None:
        destination = _resolve_collection_or_400(payload.collection_id)
        require_collection(policy, request.auth.user, destination)
        m.collection = destination
        update_fields.append("collection")
    if update_fields:
        m.save(update_fields=update_fields)
    if payload.tags is not None:
        m.tags.set(payload.tags)

    return 200, m


@router.delete(
    "/audio/{audio_id}/",
    response={204: None, 404: dict},
    summary="Delete an audio file from the Wagtail media library",
    auth=scoped("wagtailmedia.delete_media"),
)
def delete_audio(request: HttpRequest, audio_id: int):
    from wagtailmedia.models import get_media_model

    Media = get_media_model()
    try:
        m = Media.objects.get(pk=audio_id, type="audio")
    except Media.DoesNotExist:
        return 404, {"detail": "Audio not found"}

    require_instance(media_policy(), request.auth.user, "delete", m)
    m.delete()
    return 204, None
