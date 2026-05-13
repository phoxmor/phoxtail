import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .factories import (
    BlockFactory,
    BlockVariantFactory,
    VariantCollectionFactory,
)

pytestmark = pytest.mark.django_db


class TestBlock:
    def test_str(self, block):
        assert str(block) == block.name

    def test_default_variant_returns_default(self, block, collection):
        BlockVariantFactory(block=block, collection=collection, is_default=True)
        assert block.default_variant is not None
        assert block.default_variant.is_default is True

    def test_default_variant_returns_none_when_no_default(self, block):
        assert block.default_variant is None


class TestVariantCollection:
    def test_str(self, collection):
        assert str(collection) == collection.name


class TestBlockVariant:
    def test_str(self, variant):
        expected = f"{variant.block.name} | {variant.name} ({variant.collection.name})"
        assert str(variant) == expected

    def test_unique_block_collection_identifier(self, block, collection):
        BlockVariantFactory(block=block, collection=collection, identifier="same_id")
        with pytest.raises(IntegrityError):
            BlockVariantFactory(block=block, collection=collection, identifier="same_id")

    def test_unique_default_per_block(self, block, collection):
        BlockVariantFactory(block=block, collection=collection, is_default=True)
        col2 = VariantCollectionFactory()
        with pytest.raises(IntegrityError):
            BlockVariantFactory(block=block, collection=col2, is_default=True)

    def test_different_blocks_can_each_have_default(self):
        v1 = BlockVariantFactory(is_default=True)
        v2 = BlockVariantFactory(is_default=True)
        assert v1.block != v2.block


class TestSharedBlock:
    def test_clean_rejects_non_shared_block(self):
        from phoxtail.streams.models import SharedBlock

        block = BlockFactory(is_shared=False)
        sb = SharedBlock(block=block)
        with pytest.raises(ValidationError) as exc_info:
            sb.clean()
        assert "block" in exc_info.value.message_dict
