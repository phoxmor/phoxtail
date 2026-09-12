"""Schemas for the media API.

Moved verbatim from the content domain when media took ownership of its own
surface: these describe ``PhoxtailImage``, ``PhoxtailDocument`` and
``PhoxtailMedia``, which are this app's models, reached through Wagtail's
swappable getters.
"""

from __future__ import annotations

from ninja import Schema


class FocalPoint(Schema):
    x: int
    y: int
    width: int
    height: int


class ImageItem(Schema):
    id: int
    title: str
    width: int
    height: int
    description: str = ""
    tags: list[str] = []
    focal_point: FocalPoint | None = None
    file_url: str | None = None
    collection_id: int | None = None


class ImageList(Schema):
    items: list[ImageItem]
    total: int


class ImagePatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    focal_point: FocalPoint | None = None
    collection_id: int | None = None


# ---------------------------------------------------------------------------
# Page-types discovery
# ---------------------------------------------------------------------------


class DocumentItem(Schema):
    id: int
    title: str
    description: str = ""
    tags: list[str] = []
    file_size: int | None = None
    filename: str = ""
    file_extension: str = ""
    file_url: str | None = None
    collection_id: int | None = None


class DocumentList(Schema):
    items: list[DocumentItem]
    total: int


class DocumentPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    collection_id: int | None = None


class VideoItem(Schema):
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


class VideoList(Schema):
    items: list[VideoItem]
    total: int


class VideoPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    collection_id: int | None = None


class AudioItem(Schema):
    id: int
    title: str
    description: str = ""
    duration: float = 0.0
    tags: list[str] = []
    file_url: str | None = None
    collection_id: int | None = None


class AudioList(Schema):
    items: list[AudioItem]
    total: int


class AudioPatch(Schema):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    duration: float | None = None
    collection_id: int | None = None


class Error(Schema):
    detail: str
    title: str | None = None
