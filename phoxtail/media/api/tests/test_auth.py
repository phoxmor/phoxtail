"""What each media endpoint asks of its caller.

The twenty-one endpoints asked for nothing beyond being authenticated. Any
account could list every image on the site, move a document between
collections, or delete a video.

**This domain answers the person's half inside the function, not at the
door.** Wagtail grants file permissions per collection — ``(group,
collection, permission)`` — and a grant flows down to every descendant. So
``has_perm`` is False for someone Wagtail genuinely allows, and ``guarded()``
would refuse them. The endpoints carry ``scoped()`` for the credential and
ask the collection question in the body, where the file is known.

These tests are therefore about collections, not codenames. What is worth
pinning is the behaviour a global check would get wrong: a grant reaching
descendants, not reaching siblings, and a listing narrowing rather than
refusing.
"""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

IMAGES = "/media/v1/images/"


def test_unauthenticated_request_is_401(db, raw_client):
    """No caller at all is a different event from the wrong caller."""
    assert raw_client.get(IMAGES).status_code == 401


class TestReading:
    def test_a_listing_narrows_rather_than_refusing(self, raw_client, regular_user, marketing, finance, image_in):
        """Being shown nothing is a true answer to "what may I see".

        A 403 would say the act was forbidden; an empty list says the
        library holds nothing for them. Wagtail's own listings narrow.
        """
        image_in(marketing, title="Campaign")
        image_in(finance, title="Invoice")

        response = raw_client.get(IMAGES, user=regular_user)
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_a_grant_shows_only_that_collection(self, raw_client, regular_user, grant, marketing, finance, image_in):
        image_in(marketing, title="Campaign")
        image_in(finance, title="Invoice")
        user = grant(regular_user, "wagtailimages", "choose_image", marketing)

        titles = [item["title"] for item in raw_client.get(IMAGES, user=user).json()["items"]]
        assert titles == ["Campaign"]

    def test_a_grant_reaches_descendants(self, raw_client, regular_user, grant, marketing, image_in):
        """The reason the check asks the policy instead of comparing ids.

        A grant on a parent covers every collection beneath it, to any
        depth, and only the policy knows how far that reaches.
        """
        campaigns = marketing.add_child(name="Campaigns")
        spring = campaigns.add_child(name="Spring")
        image_in(spring, title="Poster")

        user = grant(regular_user, "wagtailimages", "choose_image", marketing)
        titles = [item["title"] for item in raw_client.get(IMAGES, user=user).json()["items"]]
        assert titles == ["Poster"]

    def test_one_image_is_not_found_without_a_grant(self, raw_client, regular_user, finance, image_in):
        """404, not 403 — and deliberately, copying Wagtail's chooser.

        A caller with no grant anywhere would otherwise be able to map the
        library by asking for id after id and reading which answer came
        back. Wagtail's chooser resolves within the permitted queryset for
        the same reason, so a file you may not see is a file that is not
        there.
        """
        image = image_in(finance, title="Invoice")
        assert raw_client.get(f"{IMAGES}{image.id}/", user=regular_user).status_code == 404

    def test_a_missing_image_and_a_forbidden_one_read_alike(self, raw_client, regular_user, finance, image_in):
        """The property the previous test protects, stated on its own."""
        image = image_in(finance, title="Invoice")
        forbidden = raw_client.get(f"{IMAGES}{image.id}/", user=regular_user)
        missing = raw_client.get(f"{IMAGES}{image.id + 10_000}/", user=regular_user)
        assert forbidden.status_code == missing.status_code == 404
        assert forbidden.json() == missing.json()

    def test_serving_the_bytes_needs_more_than_choosing(self, raw_client, regular_user, grant, marketing, image_in):
        """``/view/`` hands back the file itself, so it asks what Wagtail asks.

        ``wagtail.images.views.images.preview`` requires "change" before
        serving one image's bytes, where the chooser requires only "choose"
        for its metadata. A caller who may reference an image is not thereby
        allowed to download it.
        """
        image = image_in(marketing, title="Campaign")
        reader = grant(regular_user, "wagtailimages", "choose_image", marketing)
        assert raw_client.get(f"{IMAGES}{image.id}/view/", user=reader).status_code == 403

        editor = grant(reader, "wagtailimages", "change_image", marketing)
        response = raw_client.get(f"{IMAGES}{image.id}/view/", user=editor)
        assert response.status_code == 200
        assert response.content[:3] == b"\xff\xd8\xff"  # a JPEG, as promised

    def test_serving_an_svg_does_not_try_to_rasterise_it(self, raw_client, regular_user, grant, marketing, svg_in):
        """The case the live library is actually made of.

        The rendition spec names ``format-jpeg``, which Wagtail refuses for a
        vector file — so before ``preserve-svg`` this endpoint answered 500
        for every SVG, and a test using a generated PNG would never have
        noticed. Most logos are SVGs.
        """
        image = svg_in(marketing, title="Wordmark")
        user = grant(regular_user, "wagtailimages", "change_image", marketing)

        response = raw_client.get(f"{IMAGES}{image.id}/view/", user=user)
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert response.content.startswith(b"<svg")

    def test_one_image_is_served_with_a_grant(self, raw_client, regular_user, grant, marketing, image_in):
        image = image_in(marketing, title="Campaign")
        user = grant(regular_user, "wagtailimages", "choose_image", marketing)
        assert raw_client.get(f"{IMAGES}{image.id}/", user=user).status_code == 200


class TestWriting:
    def test_uploading_needs_the_destination_collection(self, raw_client, regular_user, grant, marketing, finance, png):
        """A grant does not travel sideways, which is the whole point of one."""
        user = grant(regular_user, "wagtailimages", "add_image", marketing)

        response = raw_client.post(
            IMAGES,
            data={"title": "Anything", "collection_id": finance.id},
            FILES={"file": SimpleUploadedFile("anything.png", png, content_type="image/png")},
            user=user,
        )
        assert response.status_code == 403

    def test_uploading_into_the_granted_collection_works(self, raw_client, regular_user, grant, marketing, png):
        """The other side of it — the grant is real, not merely narrow."""
        user = grant(regular_user, "wagtailimages", "add_image", marketing)

        response = raw_client.post(
            IMAGES,
            data={"title": "Campaign", "collection_id": marketing.id},
            FILES={"file": SimpleUploadedFile("campaign.png", png, content_type="image/png")},
            user=user,
        )
        assert response.status_code == 201

    def test_deleting_needs_more_than_reading(self, raw_client, regular_user, grant, marketing, image_in):
        image = image_in(marketing, title="Campaign")
        user = grant(regular_user, "wagtailimages", "choose_image", marketing)
        assert raw_client.delete(f"{IMAGES}{image.id}/", user=user).status_code == 403

    def test_add_permission_covers_your_own_uploads(self, raw_client, regular_user, grant, marketing, image_in):
        """Wagtail's ownership rule, which a collection check alone would miss.

        Holding only ``add`` in a collection still permits changing and
        deleting the files you uploaded yourself — so the owner is part of
        the answer, and the instance has to be passed to the policy.
        """
        mine = image_in(marketing, title="Mine", owner=regular_user)
        theirs = image_in(marketing, title="Theirs")
        user = grant(regular_user, "wagtailimages", "add_image", marketing)

        assert raw_client.delete(f"{IMAGES}{mine.id}/", user=user).status_code == 204
        assert raw_client.delete(f"{IMAGES}{theirs.id}/", user=user).status_code == 403

    def test_moving_a_file_asks_the_destination(self, raw_client, regular_user, grant, marketing, finance, image_in):
        """Otherwise change-here would quietly imply add-anywhere."""
        image = image_in(marketing, title="Campaign", owner=regular_user)
        user = grant(regular_user, "wagtailimages", "add_image", marketing)

        response = raw_client.patch(
            f"{IMAGES}{image.id}/",
            json={"collection_id": finance.id},
            user=user,
        )
        assert response.status_code == 403


def test_every_resource_asks_the_destination_on_a_move(
    raw_client, regular_user, grant, marketing, finance, image_in, document_in, media_in
):
    """All four resources, not only the one the other tests exercise.

    Each was written separately, so "we handled the move" has to be asked of
    each separately — the first pass here added the check to images and
    documents and missed videos and audio entirely.
    """
    user = regular_user
    for app, codename in [
        ("wagtailimages", "add_image"),
        ("wagtaildocs", "add_document"),
        ("wagtailmedia", "add_media"),
    ]:
        user = grant(user, app, codename, marketing)

    cases = [
        ("images", image_in(marketing, title="Campaign", owner=regular_user)),
        ("documents", document_in(marketing, title="Brief", owner=regular_user)),
        ("videos", media_in(marketing, kind="video", title="Clip", owner=regular_user)),
        ("audio", media_in(marketing, kind="audio", title="Jingle", owner=regular_user)),
    ]
    for resource, obj in cases:
        response = raw_client.patch(
            f"/media/v1/{resource}/{obj.id}/",
            json={"collection_id": finance.id},
            user=user,
        )
        assert response.status_code == 403, resource
        obj.refresh_from_db()
        assert obj.collection_id == marketing.id, resource


def test_superuser_is_still_admitted(client, marketing, image_in):
    """Unchanged for them: the policy answers True for a superuser."""
    image_in(marketing, title="Campaign")
    assert client.get(IMAGES).json()["total"] == 1


@pytest.mark.parametrize(
    "path",
    ["/media/v1/images/", "/media/v1/documents/", "/media/v1/videos/", "/media/v1/audio/"],
)
def test_every_listing_is_narrowed(raw_client, regular_user, path):
    """All four resources, not only the one the other tests exercise."""
    response = raw_client.get(path, user=regular_user)
    assert response.status_code == 200
    assert response.json()["total"] == 0
