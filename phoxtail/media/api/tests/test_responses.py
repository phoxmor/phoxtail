"""Every media response is shaped by its schema, reads and writes alike.

An upload and a patch answer with the same body a read gives afterwards,
and each kind carries the fields that are its own: a document its file
facts, audio and video their duration, an image its focal point.
"""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from wagtail.documents import get_document_model

pytestmark = pytest.mark.django_db


def _upload(client, kind, filename, content, **form):
    response = client.post(
        f"/media/v1/{kind}/",
        data={"title": f"Test {kind}", **form},
        FILES={"file": SimpleUploadedFile(filename, content)},
    )
    assert response.status_code == 201, response.content
    return response.json()


def _patch_then_read(client, kind, item_id, change):
    patched = client.patch(f"/media/v1/{kind}/{item_id}/", json=change)
    assert patched.status_code == 200, patched.content
    read = client.get(f"/media/v1/{kind}/{item_id}/").json()
    assert patched.json() == read
    return read


def test_an_image_answers_the_same_after_upload_patch_and_read(client, png):
    uploaded = _upload(client, "images", "logo.png", png)
    assert uploaded["file_url"] and uploaded["width"] == 1

    read = _patch_then_read(
        client,
        "images",
        uploaded["id"],
        {"tags": ["brand"], "focal_point": {"x": 0, "y": 0, "width": 1, "height": 1}},
    )

    assert read["tags"] == ["brand"]
    assert read["focal_point"] == {"x": 0, "y": 0, "width": 1, "height": 1}
    (listed,) = client.get("/media/v1/images/").json()["items"]
    assert listed == read


def test_a_document_carries_its_file_facts(client):
    uploaded = _upload(client, "documents", "brief.pdf", b"%PDF-1.4 brief", description="A brief.")

    read = _patch_then_read(client, "documents", uploaded["id"], {"tags": ["legal"]})

    # Storage renames the file when another test saved a brief.pdf first,
    # so the stored name is the one to compare with.
    stored = get_document_model().objects.get(pk=uploaded["id"])
    assert read["filename"] == stored.filename
    assert read["filename"].startswith("brief")
    assert read["file_extension"] == "pdf"
    assert read["file_size"] == len(b"%PDF-1.4 brief")
    assert read["description"] == "A brief."
    assert read["tags"] == ["legal"]
    assert read["file_url"]
    (listed,) = client.get("/media/v1/documents/").json()["items"]
    assert listed == read


@pytest.mark.parametrize("kind, filename", [("audio", "clip.mp3"), ("videos", "clip.mp4")])
def test_audio_and_video_carry_their_duration(client, kind, filename):
    uploaded = _upload(client, kind, filename, b"not decoded here", duration="42.5")

    read = _patch_then_read(client, kind, uploaded["id"], {"tags": ["promo"]})

    assert read["duration"] == 42.5
    assert read["tags"] == ["promo"]
    assert read["file_url"]
    (listed,) = client.get(f"/media/v1/{kind}/").json()["items"]
    assert listed == read
