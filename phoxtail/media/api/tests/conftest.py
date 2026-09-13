"""Fixtures for media v1 API tests.

Run against the real shared ``phoxtail.api`` instance, so the tests exercise
the production wiring: the media router found at ``/media/v1/`` because the
app ships ``phoxtail/media/api/`` declaring ``versions``.

The collection tree is the point of these fixtures. Wagtail grants file
permissions per collection, so a test that never builds one cannot tell a
working check from a missing one.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, Permission
from ninja.testing import TestClient


class AuthedClient:
    """TestClient wrapper that authenticates every request as ``user``."""

    def __init__(self, client: TestClient, user):
        self._client = client
        self._user = user

    def __getattr__(self, method):
        def call(*args, **kwargs):
            kwargs.setdefault("user", self._user)
            return getattr(self._client, method)(*args, **kwargs)

        return call


@pytest.fixture(scope="session")
def raw_client():
    from phoxtail.api import api

    return TestClient(api)


@pytest.fixture
def root_collection(db):
    from wagtail.models import Collection

    return Collection.get_first_root_node()


@pytest.fixture
def marketing(root_collection):
    return root_collection.add_child(name="Marketing")


@pytest.fixture
def finance(root_collection):
    """A sibling of Marketing, to prove a grant does not travel sideways."""
    return root_collection.add_child(name="Finance")


@pytest.fixture
def superuser(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username="media-admin",
        email="media-admin@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def regular_user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="media-member",
        email="media-member@example.invalid",
        password="irrelevant",
    )


@pytest.fixture
def client(raw_client, superuser):
    return AuthedClient(raw_client, superuser)


@pytest.fixture
def grant():
    """Grant a Wagtail file permission on one collection, and only there.

    Returns a fresh user instance: Django caches permissions on the object at
    first lookup, and the request is served with the instance the test holds.
    """
    from wagtail.models import GroupCollectionPermission

    def _grant(user, app_label: str, codename: str, collection):
        group, _ = Group.objects.get_or_create(name=f"{collection.name} {codename}")
        user.groups.add(group)
        GroupCollectionPermission.objects.create(
            group=group,
            collection=collection,
            permission=Permission.objects.get(content_type__app_label=app_label, codename=codename),
        )
        return type(user).objects.get(pk=user.pk)

    return _grant


@pytest.fixture
def png():
    """A real one-pixel PNG.

    Written by Pillow rather than inlined as hex: Wagtail opens the file to
    read its dimensions, so a plausible-looking byte string is not enough —
    it has to decode.
    """
    import io

    from PIL import Image as PILImage

    buffer = io.BytesIO()
    PILImage.new("RGB", (1, 1)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def image_in(db, png):
    """An image sitting in a given collection, owned by nobody in particular."""
    from django.core.files.base import ContentFile
    from wagtail.images import get_image_model

    def _image(collection, title="Logo", owner=None):
        Image = get_image_model()
        # Wagtail's ownership rule reads ``uploaded_by_user``, not ``owner``
        # — the policy is constructed with that field name.
        return Image.objects.create(
            title=title,
            file=ContentFile(png, name=f"{title.lower()}.png"),
            collection=collection,
            uploaded_by_user=owner,
            width=1,
            height=1,
        )

    return _image


@pytest.fixture
def document_in(db):
    """A document in a given collection. Any bytes will do — nothing reads it."""
    from django.core.files.base import ContentFile
    from wagtail.documents import get_document_model

    def _document(collection, title="Brief", owner=None):
        Document = get_document_model()
        return Document.objects.create(
            title=title,
            file=ContentFile(b"%PDF-1.4 ", name=f"{title.lower()}.pdf"),
            collection=collection,
            uploaded_by_user=owner,
        )

    return _document


@pytest.fixture
def media_in(db):
    """A video or audio file in a given collection.

    wagtailmedia stores the upload without decoding it, so the bytes are
    arbitrary — duration and dimensions are plain fields, not measurements.
    """
    from django.core.files.base import ContentFile
    from wagtailmedia.models import get_media_model

    def _media(collection, kind="video", title="Clip", owner=None):
        Media = get_media_model()
        return Media.objects.create(
            title=title,
            file=ContentFile(b"not really encoded", name=f"{title.lower()}.mp4"),
            type=kind,
            duration=1,
            collection=collection,
            uploaded_by_user=owner,
        )

    return _media


@pytest.fixture
def svg_in(db):
    """An SVG image in a given collection.

    Wagtail treats SVGs as images but cannot rasterise them, so any endpoint
    that names a ``format-*`` filter has a second case to answer.
    """
    from django.core.files.base import ContentFile
    from wagtail.images import get_image_model

    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'

    def _svg(collection, title="Wordmark", owner=None):
        Image = get_image_model()
        return Image.objects.create(
            title=title,
            file=ContentFile(svg, name=f"{title.lower()}.svg"),
            collection=collection,
            uploaded_by_user=owner,
            width=1,
            height=1,
        )

    return _svg
