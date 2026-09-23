"""Admin sync reads a remote's variants whole, or says why it could not.

Sync states compare every local variant with every remote one, so the
remote's list is read page by page to the end, and anything short of the
whole list becomes a message on the page rather than a state decided from
part of it.
"""

from __future__ import annotations

import pytest
from django.test import RequestFactory

from phoxtail.core.paging import ListChanged, NotAPagedList
from phoxtail.remotes.models import Remote
from phoxtail.streams.admin.sync.views import _remote_variants, _unreadable, admin_sync_streams
from phoxtail.streams.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

BASE = "https://remote.example.com"
VARIANTS = f"{BASE}/api/streams/v1/variants/"


def _variant(index):
    return {
        "id": index,
        "identifier": f"variant_{index}",
        "name": f"Variant {index}",
        "block": {"identifier": "hero", "name": "Hero", "page_types": [], "source_app": ""},
        "collection": None,
        "content_hash": "",
    }


@pytest.fixture
def remote():
    return Remote.objects.create(name="Remote", base_url=BASE, token="token")


def test_every_page_of_the_remote_list_is_read(remote, httpx_mock):
    rows = [_variant(index) for index in range(3)]
    httpx_mock.add_response(url=f"{VARIANTS}?block=hero&limit=500&offset=0", json={"items": rows[:2], "total": 3})
    httpx_mock.add_response(url=f"{VARIANTS}?block=hero&limit=500&offset=2", json={"items": rows[2:], "total": 3})

    assert [row["id"] for row in _remote_variants(remote, block="hero")] == [0, 1, 2]


def test_a_failed_request_is_not_read_as_an_empty_list(remote, httpx_mock):
    httpx_mock.add_response(status_code=503)

    with pytest.raises(Exception, match="503"):
        _remote_variants(remote)


@pytest.mark.parametrize(
    "exc, words",
    [
        (NotAPagedList("old"), "older phoxtail"),
        (ListChanged("moved"), "changed while they were being read"),
    ],
)
def test_each_way_of_falling_short_has_its_own_words(exc, words):
    assert words in _unreadable(exc)


def test_browsing_a_remote_on_an_older_phoxtail_says_so(remote, httpx_mock):
    httpx_mock.add_response(json={"variants": [_variant(0)], "total": 1})
    request = RequestFactory().get("/", {"remote": remote.pk, "mode": "remote"})
    request.user = UserFactory(is_superuser=True, is_staff=True)

    response = admin_sync_streams(request)

    assert response.status_code == 200
    assert "older phoxtail" in response.content.decode()
