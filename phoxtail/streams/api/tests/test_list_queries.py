"""A streams list costs the same number of queries at any length.

Each row carries related rows — a variant its block, collection, page types
and preview images; a block its variant count; a shared block its block,
site, locale and variant. They arrive with the list's query, and a lookup
per row is what would creep back without a count.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from phoxtail.streams.tests.factories import BlockFactory, BlockVariantFactory
from phoxtail.streams.tests.test_block_site_slots import fill_shared_content, make_site_wide_block

pytestmark = pytest.mark.django_db


def _queries(client, path):
    client.get(path)  # once untimed: per-process caches are not a cost per row
    with CaptureQueriesContext(connection) as captured:
        response = client.get(path)
    assert response.status_code == 200
    return len(captured.captured_queries), response.json()["total"]


def _grows(client, path, add):
    add(1, 0)
    few, few_total = _queries(client, path)
    add(4, 1)
    many, many_total = _queries(client, path)
    assert many_total > few_total
    return few, many


def test_the_variant_list_does_not_grow_per_variant(client):
    def add(count, start):
        for _ in range(count):
            BlockVariantFactory()

    few, many = _grows(client, "/streams/v1/variants/", add)

    assert many == few


def test_the_block_list_does_not_grow_per_block(client):
    def add(count, start):
        for _ in range(count):
            BlockVariantFactory(block=BlockFactory())

    few, many = _grows(client, "/streams/v1/blocks/", add)

    assert many == few


def test_the_shared_block_list_does_not_grow_per_row(client):
    def add(count, start):
        for index in range(start, start + count):
            fill_shared_content(make_site_wide_block(identifier=f"shared_{index}"))

    few, many = _grows(client, "/streams/v1/shared-blocks/", add)

    assert many == few
