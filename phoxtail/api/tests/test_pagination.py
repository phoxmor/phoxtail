"""Every list comes back one page at a time, in one shape.

The properties worth protecting: a list endpoint cannot forget to paginate,
consecutive pages never overlap, ``total`` counts every match rather than
the page, a request past the cap is refused rather than quietly cut, and
anything that is neither a queryset nor a list is refused rather than
guessed at.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from ninja import Router as NinjaRouter
from ninja import Schema
from ninja.testing import TestClient

from phoxtail.api.pagination import MAX_LIMIT, Router, in_stable_order, unpaginated
from phoxtail.core.discovery import versioned_routers
from phoxtail.users.models import Gender

pytestmark = pytest.mark.django_db


class Row(Schema):
    name: str


class HandWrapped(Schema):
    rows: list[Row]
    total: int


def _genders(*names):
    return [Gender.objects.create(name=name) for name in names]


def _router(view):
    router = Router()
    router.get("/", response={200: list[Row], 403: Row})(view)
    return router


class TestTheShape:
    def test_a_list_response_is_paged(self):
        _genders("A", "B", "C")
        client = TestClient(_router(lambda request: Gender.objects.all()))

        body = client.get("/?limit=2").json()

        assert [row["name"] for row in body["items"]] == ["A", "B"]
        assert body["total"] == 3

    def test_offset_reads_on(self):
        _genders("A", "B", "C")
        client = TestClient(_router(lambda request: Gender.objects.all()))

        assert [row["name"] for row in client.get("/?limit=2&offset=2").json()["items"]] == ["C"]

    def test_past_the_cap_is_refused_not_cut(self):
        client = TestClient(_router(lambda request: Gender.objects.all()))

        assert client.get(f"/?limit={MAX_LIMIT + 1}").status_code == 422

    def test_a_list_built_in_memory_is_paged_in_its_own_order(self):
        client = TestClient(_router(lambda request: [Row(name=name) for name in "CBA"]))

        body = client.get("/?limit=2&offset=1").json()

        assert [row["name"] for row in body["items"]] == ["B", "A"]
        assert body["total"] == 3

    def test_search_results_are_refused(self):
        # What Wagtail's autocomplete() returns: sliceable and countable,
        # but neither a queryset to order nor a list to trust.
        class SearchResults:
            def __getitem__(self, key):
                return []

            def count(self):
                return 0

        client = TestClient(_router(lambda request: SearchResults()))

        with pytest.raises(TypeError, match="narrow_by_search"):
            client.get("/")

    def test_a_returned_error_is_not_paged(self):
        client = TestClient(_router(lambda request: (403, {"name": "no"})))

        with pytest.raises(TypeError, match="not tuple"):
            client.get("/")


class TestStableOrder:
    def test_the_primary_key_breaks_ties(self):
        qs = in_stable_order(Gender.objects.order_by("symbol"))

        assert qs.query.order_by == ("symbol", "pk")

    def test_the_model_default_ordering_is_kept(self):
        default = list(Permission._meta.ordering)
        assert default, "the model must declare an ordering for this test to mean anything"

        assert list(in_stable_order(Permission.objects.all()).query.order_by) == [*default, "pk"]

    def test_the_page_query_breaks_ties_by_primary_key(self):
        # SQLite happens to return ties in insertion order, so comparing two
        # pages would pass without the tiebreaker. The query itself cannot.
        _genders("A", "B")
        client = TestClient(_router(lambda request: Gender.objects.order_by("symbol")))
        pk_column = f'"{Gender._meta.db_table}"."{Gender._meta.pk.column}"'

        with CaptureQueriesContext(connection) as queries:
            client.get("/?limit=1")

        page = next(q["sql"] for q in queries.captured_queries if "LIMIT" in q["sql"])
        order_by = page.split("ORDER BY", 1)[1].split("LIMIT", 1)[0]
        assert order_by.strip().endswith(f"{pk_column} ASC")


class TestUnpaginated:
    def test_a_list_on_ninjas_own_router_is_found(self):
        router = NinjaRouter()
        router.get("/", response=list[Row])(lambda request: [])

        assert unpaginated(router) == ["GET /"]

    def test_a_hand_wrapped_list_is_found(self):
        router = Router()
        router.get("/", response=HandWrapped)(lambda request: {"rows": [], "total": 0})

        assert unpaginated(router) == ["GET /"]

    def test_a_paged_list_is_not(self):
        assert unpaginated(_router(lambda request: Gender.objects.all())) == []

    def test_a_write_answering_with_a_list_is_not(self):
        router = NinjaRouter()
        router.put("/", response=HandWrapped)(lambda request: {"rows": [], "total": 0})

        assert unpaginated(router) == []


class TestWrites:
    def test_a_write_answering_with_a_list_returns_it_whole(self):
        _genders("A", "B", "C")
        router = Router()
        router.post("/", response={200: list[Row]})(lambda request: Gender.objects.all())
        client = TestClient(router)

        body = client.post("/?limit=1").json()

        assert sorted(row["name"] for row in body) == ["A", "B", "C"]


# Apps whose lists still build their own envelopes. Each app's migration
# removes its name; the test below fails if a name stays after its app is done.
PENDING = {"agent", "cms", "core", "dashboard", "design", "media", "streams"}


APPS = list(versioned_routers())


@pytest.mark.parametrize("name, versions", APPS, ids=[name for name, _ in APPS])
def test_every_list_is_paged(name, versions):
    found = [f"/{name}/{version}: {op}" for version, router in versions.items() for op in unpaginated(router)]
    if name in PENDING:
        assert found, f"{name} is paginated now; remove it from PENDING."
    else:
        assert found == []
