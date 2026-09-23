"""A media list costs the same number of queries at any length.

Each item carries its tags; a list prefetches them, where reading them one
item at a time costs a query per row.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.django_db


def _queries(client, path):
    client.get(path)  # once untimed: per-process caches are not a cost per row
    with CaptureQueriesContext(connection) as captured:
        response = client.get(path)
    assert response.status_code == 200
    return len(captured.captured_queries), response.json()["total"]


def test_the_image_list_does_not_grow_per_image(client, root_collection, image_in):
    def add(count, start):
        for index in range(start, start + count):
            image_in(root_collection, title=f"Image {index}").tags.add("brand", f"tag-{index}")

    add(1, 0)
    few, few_total = _queries(client, "/media/v1/images/")
    add(4, 1)
    many, many_total = _queries(client, "/media/v1/images/")

    assert many_total == few_total + 4
    assert many == few
    assert all("brand" in item["tags"] for item in client.get("/media/v1/images/").json()["items"])
