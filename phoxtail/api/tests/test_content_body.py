"""Regression test for ``PUT /content/v1/pages/{id}/body/``.

Guards the fix in ``phoxtail.api.content.v1._helpers.replace_body``: a
malformed nested block value (a StreamBlock field inside a StructBlock
given ``[None, None]`` instead of proper ``{type, value, id}`` entries)
must be rejected with a 400 *before* anything is persisted, not accepted
and left to crash the admin editor / page renderer later. See the
incident this guards against: an agent-written page body with
``"plans": [null, null, null]`` made a live page unopenable in both the
Wagtail admin and the public renderer.
"""

from __future__ import annotations

import pytest
from ninja.testing import TestClient
from wagtail.blocks import CharBlock, StreamBlock, StructBlock

from phoxtail.cms.streams import BodyStreamField
from phoxtail.streams.cache import get_cache_generation

pytestmark = pytest.mark.django_db


class AuthedClient:
    """TestClient wrapper that authenticates every request as ``user``."""

    def __init__(self, client: TestClient, user):
        self._client = client
        self._user = user

    def __getattr__(self, method):
        def call(*args, **kwargs):
            kwargs.setdefault("user", self._user)
            kwargs.setdefault("session", {})
            return getattr(self._client, method)(*args, **kwargs)

        return call


@pytest.fixture(scope="session")
def raw_client():
    from phoxtail.api import api

    return TestClient(api)


@pytest.fixture
def superuser(django_user_model):
    return django_user_model.objects.create_superuser(
        username="content-admin",
        email="content-admin@example.com",
        password="irrelevant",
    )


@pytest.fixture
def client(raw_client, superuser):
    return AuthedClient(raw_client, superuser)


@pytest.fixture
def site_page():
    """A draft ``phoxtail_cms.SitePage`` under the default root."""
    from wagtail.models import Site

    from phoxtail.cms.models import SitePage

    root = Site.objects.get(is_default_site=True).root_page
    page = SitePage(title="Body Regression Test", slug="body-regression-test", live=False)
    root.add_child(instance=page)
    return page


@pytest.fixture
def widget_schema(monkeypatch):
    """Force ``BodyStreamField`` to expose one block type — ``widget`` — with
    a nested StreamBlock field inside a StructBlock, mirroring the real
    ``pricings.plans`` shape from the incident. Bypasses the DB-driven
    schema-authoring system entirely so the test doesn't depend on any
    catalog content being seeded."""

    class ItemBlock(StructBlock):
        label = CharBlock(required=False)

    class WidgetBlock(StructBlock):
        items = StreamBlock([("item", ItemBlock())], required=False)

    test_stream_block = StreamBlock([("widget", WidgetBlock())], required=False)
    monkeypatch.setattr(BodyStreamField, "_cached_stream_block", test_stream_block)
    monkeypatch.setattr(BodyStreamField, "_cache_generation", get_cache_generation())


def test_put_body_rejects_malformed_nested_block(client, site_page, widget_schema):
    etag = client.get(f"/content/v1/pages/{site_page.pk}/body/").headers["ETag"]

    bad_body = {
        "body": [
            {
                "type": "widget",
                "value": {"items": [None, None]},
                "id": "6db9151e-aeb4-4f2b-85f9-bb267233de45",
            }
        ]
    }
    response = client.put(
        f"/content/v1/pages/{site_page.pk}/body/",
        json=bad_body,
        headers={"If-Match": etag},
    )

    assert response.status_code == 400
    site_page.refresh_from_db()
    assert site_page.revisions.count() == 0


def test_put_body_accepts_well_formed_nested_block(client, site_page, widget_schema):
    etag = client.get(f"/content/v1/pages/{site_page.pk}/body/").headers["ETag"]

    good_body = {
        "body": [
            {
                "type": "widget",
                "value": {
                    "items": [
                        {"type": "item", "value": {"label": "First"}, "id": "a"},
                        {"type": "item", "value": {"label": "Second"}, "id": "b"},
                    ]
                },
                "id": "6db9151e-aeb4-4f2b-85f9-bb267233de45",
            }
        ]
    }
    response = client.put(
        f"/content/v1/pages/{site_page.pk}/body/",
        json=good_body,
        headers={"If-Match": etag},
    )

    assert response.status_code == 200
    site_page.refresh_from_db()
    assert site_page.revisions.count() == 1
