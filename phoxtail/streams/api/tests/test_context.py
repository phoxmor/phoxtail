"""``/context/`` briefs an agent on a block, with variants to learn from."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

PATH = "/streams/v1/context/"


def test_reference_variants_come_back_with_their_block(client, block):
    from phoxtail.streams.models import BlockVariant

    variant = BlockVariant.objects.create(block=block, identifier="reference", name="Reference", description="d")

    response = client.post(PATH, json={"block_id": block.id, "references": [variant.id]})

    assert response.status_code == 200, response.content
    (reference,) = response.json()["references"]
    assert reference["block"]["id"] == block.id
    assert reference["block"]["identifier"] == block.identifier
