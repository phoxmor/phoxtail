"""A cms list costs the same number of queries at any length.

The page list annotates each page's locale and turns pages specific once
per type; the collection list annotates each parent and prefetches the
view restrictions. Each of those replaced a lookup per row, and a lookup
per row is exactly what would creep back without a test that counts.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.django_db


def _queries(client, path):
    # Once untimed: the first request fills Wagtail's per-process caches
    # (the site's root paths), which is not a cost per row.
    client.get(path)
    with CaptureQueriesContext(connection) as captured:
        response = client.get(path)
    assert response.status_code == 200
    return len(captured.captured_queries), response.json()["total"]


def _add_pages(count, start=0):
    from wagtail.models import Page

    from phoxtail.cms.models import SitePage

    home = Page.objects.get(depth=2)
    for index in range(start, start + count):
        page = home.add_child(instance=SitePage(title=f"Page {index}", slug=f"page-{index}"))
        page.save_revision().publish()


def _add_collections(count, start=0):
    from wagtail.models import Collection, CollectionViewRestriction

    group = Group.objects.get_or_create(name="Readers")[0]
    parent = Collection.get_first_root_node().add_child(name=f"Parent {start}")
    for index in range(start, start + count):
        child = parent.add_child(name=f"Child {index}")
        restriction = CollectionViewRestriction.objects.create(collection=child, restriction_type="groups")
        restriction.groups.add(group)


def test_the_page_list_does_not_grow_per_page(client):
    _add_pages(1)
    few, few_total = _queries(client, "/cms/v1/pages/")
    _add_pages(4, start=1)
    many, many_total = _queries(client, "/cms/v1/pages/")

    assert many_total == few_total + 4
    assert many == few


def test_the_collection_list_does_not_grow_per_collection(client):
    _add_collections(1)
    few, few_total = _queries(client, "/cms/v1/collections/")
    _add_collections(4, start=1)
    many, many_total = _queries(client, "/cms/v1/collections/")

    assert many_total == few_total + 5
    assert many == few


def test_a_collection_read_without_the_list_query_still_names_its_parent():
    from wagtail.models import Collection

    from phoxtail.cms.api.v1.collections import CollectionItem

    parent = Collection.get_first_root_node().add_child(name="Parent")
    child = parent.add_child(name="Child")

    item = CollectionItem.from_orm(Collection.objects.get(pk=child.pk))

    assert item.parent_id == parent.pk
    assert item.view_restriction is None
