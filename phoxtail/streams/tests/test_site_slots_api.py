"""The streams v1 API and sync envelope carry the site-wide slot fields."""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from ninja.errors import HttpError

from phoxtail.streams.api.v1._helpers import (
    block_detail,
    block_summary,
    build_variant_envelope,
    shared_block_etag,
    shared_block_summary,
)
from phoxtail.streams.api.v1.schemas import SharedBlockCreate, SharedBlockUpdate
from phoxtail.streams.api.v1.shared_blocks import (
    create_shared_block,
    update_shared_block_by_id,
)
from phoxtail.streams.models import Block
from phoxtail.streams.tests.factories import BlockFactory, BlockVariantFactory
from phoxtail.streams.tests.test_block_site_slots import (
    fill_shared_content,
    make_site_wide_block,
)

pytestmark = pytest.mark.django_db


def _patch(shared_block, **fields):
    request = RequestFactory().patch("/", HTTP_IF_MATCH=shared_block_etag(shared_block))
    return update_shared_block_by_id(request, HttpResponse(), shared_block.pk, SharedBlockUpdate(**fields))


class TestBlockSerializers:
    def test_summary_and_detail_carry_slot_fields(self):
        block = BlockFactory(is_shared=True, site_slot="head_start", slot_order=3, render_in_preview=False)
        for data in (block_summary(block, 0), block_detail(block)):
            assert data["site_slot"] == "head_start"
            assert data["slot_order"] == 3
            assert data["render_in_preview"] is False


class TestSharedBlockVariant:
    def test_summary_carries_variant(self):
        block = make_site_wide_block()
        variant = BlockVariantFactory(block=block, collection=None)
        row = fill_shared_content(block, variant=variant)
        data = shared_block_summary(row)
        assert data["variant_id"] == variant.pk
        assert data["variant_identifier"] == variant.identifier

    def test_patch_sets_and_clears_variant(self):
        block = make_site_wide_block()
        variant = BlockVariantFactory(block=block, collection=None)
        row = fill_shared_content(block)

        data = _patch(row, variant_id=variant.pk)
        assert data["variant_id"] == variant.pk

        row.refresh_from_db()
        data = _patch(row, variant_id=None)
        assert data["variant_id"] is None

    def test_patch_without_variant_key_leaves_it_untouched(self):
        block = make_site_wide_block()
        variant = BlockVariantFactory(block=block, collection=None)
        row = fill_shared_content(block, variant=variant)
        data = _patch(row, content=[{"type": block.identifier, "value": {"title": "New"}, "id": "t"}])
        assert data["variant_id"] == variant.pk

    def test_create_rejects_variant_of_another_block(self):
        block = make_site_wide_block()
        stranger = BlockVariantFactory()
        row = fill_shared_content(block)  # occupies default site+locale
        payload = SharedBlockCreate(
            block_id=block.pk,
            site_id=row.site_id,
            locale_id=row.locale_id,
            variant_id=stranger.pk,
            content=[{"type": block.identifier, "value": {"title": "x"}, "id": "t"}],
        )
        request = RequestFactory().post("/")
        with pytest.raises(HttpError) as exc_info:
            create_shared_block(request, HttpResponse(), payload)
        assert exc_info.value.status_code == 400


class TestPushEnvelope:
    def test_slot_fields_survive_a_push_round_trip(self):
        from phoxtail.streams.services.sync import apply_variant_envelope

        block = make_site_wide_block(identifier="gtm", slot="body_end")
        block.slot_order = 5
        block.render_in_preview = False
        block.save()
        variant = block.variants.get()
        envelope = build_variant_envelope(variant)
        assert envelope["block"]["site_slot"] == "body_end"

        block.delete()  # simulate the receiving project
        apply_variant_envelope(envelope)

        installed = Block.objects.get(identifier="gtm")
        assert installed.site_slot == "body_end"
        assert installed.slot_order == 5
        assert installed.render_in_preview is False
