"""Schemas for the media API.

These describe ``PhoxtailImage``, ``PhoxtailDocument`` and ``PhoxtailMedia``,
this app's models, reached through Wagtail's swappable getters. Responses
are shaped here, from the instances the endpoints return.
"""

from __future__ import annotations

from ninja import Schema

from phoxtail.core.utils import public_url


def file_url(obj, field_name: str = "file") -> str | None:
    """The public URL of *obj*'s file, or None when there is none to give."""
    stored = getattr(obj, field_name, None)
    if not stored:
        return None
    try:
        raw = stored.url
    except (ValueError, AttributeError):
        return None
    return public_url(raw)


class _Media(Schema):
    """What every media item answers the same way."""

    @staticmethod
    def resolve_description(item) -> str:
        return getattr(item, "description", "") or ""

    @staticmethod
    def resolve_tags(item) -> list[str]:
        # Read through the prefetch a list makes, not tags.names(), which
        # queries again for every row.
        return [tag.name for tag in item.tags.all()]

    @staticmethod
    def resolve_file_url(item) -> str | None:
        return file_url(item)


class FocalPoint(Schema):
    x: int
    y: int
    width: int
    height: int


class ImageItem(_Media):
    id: int
    title: str
    width: int
    height: int
    description: str = ""
    tags: list[str] = []
    focal_point: FocalPoint | None = None
    file_url: str | None = None
    collection_id: int | None = None

    @staticmethod
    def resolve_focal_point(image) -> dict | None:
        point = (image.focal_point_x, image.focal_point_y, image.focal_point_width, image.focal_point_height)
        if any(value is None for value in point):
            return None
        return dict(zip(("x", "y", "width", "height"), point))


class ImagePatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    focal_point: FocalPoint | None = None
    collection_id: int | None = None


# ---------------------------------------------------------------------------
# Page-types discovery
# ---------------------------------------------------------------------------


class DocumentItem(_Media):
    id: int
    title: str
    description: str = ""
    tags: list[str] = []
    file_size: int | None = None
    filename: str = ""
    file_extension: str = ""
    file_url: str | None = None
    collection_id: int | None = None


class DocumentPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    collection_id: int | None = None


class VideoItem(_Media):
    id: int
    title: str
    description: str = ""
    duration: float = 0.0
    width: int | None = None
    height: int | None = None
    tags: list[str] = []
    file_url: str | None = None
    thumbnail_url: str | None = None
    collection_id: int | None = None

    @staticmethod
    def resolve_thumbnail_url(video) -> str | None:
        return file_url(video, "thumbnail")


class VideoPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    collection_id: int | None = None


class AudioItem(_Media):
    id: int
    title: str
    description: str = ""
    duration: float = 0.0
    tags: list[str] = []
    file_url: str | None = None
    collection_id: int | None = None


class AudioPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    duration: float | None = None
    collection_id: int | None = None


class Error(Schema):
    detail: str
    title: str | None = None
