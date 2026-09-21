"""Where a file URL says the file lives.

The API is called from more than one address: a browser on the site's own
domain, and the MCP server at ``http://web`` inside the compose network.
A ``file_url`` built from the request's ``Host`` header echoes whichever of
those asked — and ``http://web/media/…`` is unreachable to anyone the MCP
server hands it to. The origin comes from the project's configuration.
"""

from __future__ import annotations

import pytest
from django.core.files.base import ContentFile

from phoxtail.core.utils import public_url

ORIGIN = "https://example.com"


@pytest.fixture
def origin(settings):
    settings.WAGTAILADMIN_BASE_URL = ORIGIN


def test_a_relative_path_joins_the_configured_origin(origin):
    assert public_url("/media/x.png") == f"{ORIGIN}/media/x.png"


def test_an_absolute_url_passes_through(origin):
    """A remote storage backend already says where its files live."""
    assert public_url("https://cdn.example.net/x.png") == "https://cdn.example.net/x.png"


def test_nothing_stays_nothing(origin):
    assert public_url(None) is None
    assert public_url("") is None


@pytest.mark.usefixtures("origin")
def test_every_resource_is_built_on_the_configured_origin(client, marketing, image_in, document_in, media_in):
    resources = [
        ("images", image_in(marketing)),
        ("documents", document_in(marketing)),
        ("videos", media_in(marketing, kind="video")),
        ("audio", media_in(marketing, kind="audio")),
    ]
    for path, obj in resources:
        response = client.get(f"/media/v1/{path}/{obj.id}/", headers={"Host": "web"})
        assert response.status_code == 200, path
        assert response.json()["file_url"] == f"{ORIGIN}{obj.file.url}", path


@pytest.mark.usefixtures("origin")
def test_a_video_thumbnail_is_built_the_same_way(client, marketing, media_in):
    video = media_in(marketing, kind="video")
    video.thumbnail = ContentFile(b"not really a jpeg", name="clip.jpg")
    video.save()

    response = client.get(f"/media/v1/videos/{video.id}/", headers={"Host": "web"})

    assert response.json()["thumbnail_url"] == f"{ORIGIN}{video.thumbnail.url}"
