"""The internal-link list pages and searches like every other list."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from phoxtail.core.models import InternalLink

BASE = "/core/v1/internal-links/"


def _links(*labels):
    # Created directly: url_name must be unique, and need not resolve here.
    return [InternalLink.objects.create(label=label, url_name=f"test:{label.lower()}") for label in labels]


def test_the_list_answers_one_page_and_the_total(client):
    _links("Alpha", "Beta", "Gamma")

    body = client.get(f"{BASE}?limit=2&offset=1").json()

    assert [item["label"] for item in body["items"]] == ["Beta", "Gamma"]
    assert body["total"] == 3


def test_search_narrows_the_list(client):
    # The SQLite fallback backend may match nothing, so this pins that a
    # search is answered at all: returning Wagtail's own results instead of
    # a narrowed queryset cannot be paged, and fails the request.
    _links("Alpha")

    response = client.get(f"{BASE}?search=Alp")

    assert response.status_code == 200
    assert set(response.json()) == {"items", "total"}


def test_identifiers_and_timestamps_are_typed(client):
    (link,) = _links("Alpha")

    body = client.get(f"{BASE}{link.pk}/").json()

    assert UUID(body["uuid"]) == link.uuid
    assert datetime.fromisoformat(body["created_at"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(body["updated_at"].replace("Z", "+00:00"))


def test_a_link_without_a_creation_time_still_reads(client):
    # created_at is nullable on the model, so a row from before it was
    # recorded must serialize rather than fail.
    (link,) = _links("Alpha")
    InternalLink.objects.filter(pk=link.pk).update(created_at=None)

    assert client.get(f"{BASE}{link.pk}/").json()["created_at"] is None
