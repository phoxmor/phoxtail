import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .factories import (
    BlockFactory,
    BlockSystemPromptFactory,
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

    def test_render_empty_template(self):
        col = VariantCollectionFactory(template="")
        assert col.render() == ""

    def test_render_with_template(self):
        col = VariantCollectionFactory(template="Name: {{ object.name }}")
        result = col.render()
        assert col.name in result


class TestBlockVariant:
    def test_str(self, variant):
        expected = f"{variant.block.name} | {variant.name} ({variant.collection.name})"
        assert str(variant) == expected

    def test_unique_block_collection_identifier(self, block, collection):
        BlockVariantFactory(block=block, collection=collection, identifier="same_id")
        with pytest.raises(IntegrityError):
            BlockVariantFactory(
                block=block, collection=collection, identifier="same_id"
            )

    def test_unique_default_per_block(self, block, collection):
        BlockVariantFactory(block=block, collection=collection, is_default=True)
        col2 = VariantCollectionFactory()
        with pytest.raises(IntegrityError):
            BlockVariantFactory(block=block, collection=col2, is_default=True)

    def test_different_blocks_can_each_have_default(self):
        v1 = BlockVariantFactory(is_default=True)
        v2 = BlockVariantFactory(is_default=True)
        assert v1.block != v2.block


class TestBlockSystemPrompt:
    def test_str(self, system_prompt):
        assert str(system_prompt) == system_prompt.name

    def test_clean_valid_template(self):
        sp = BlockSystemPromptFactory(template="{{ block.name }}")
        sp.clean()  # should not raise

    def test_clean_invalid_template(self):
        sp = BlockSystemPromptFactory(template="{% invalid_tag %}")
        with pytest.raises(ValidationError) as exc_info:
            sp.clean()
        assert "template" in exc_info.value.message_dict

    def test_render_with_variant_and_collection(self, variant, collection):
        sp = BlockSystemPromptFactory(
            template="Block: {{ block.name }}, Variant: {{ variant.name }}, "
            "Collection: {{ collection.name }}"
        )
        result = sp.render(variant=variant, collection=collection)
        assert variant.block.name in result
        assert variant.name in result
        assert collection.name in result

    def test_render_with_references(self, variant, collection):
        ref = BlockVariantFactory(collection=collection)
        sp = BlockSystemPromptFactory(
            template="{% for r in references %}{{ r.name }}{% endfor %}"
        )
        result = sp.render(variant=variant, collection=collection, references=[ref])
        assert ref.name in result

    def test_render_empty_references(self, variant, collection):
        sp = BlockSystemPromptFactory(template="Refs: {{ references|length }}")
        result = sp.render(variant=variant, collection=collection)
        assert "Refs: 0" in result

    def test_render_none_variant(self):
        sp = BlockSystemPromptFactory(template="Block: {{ block }}")
        result = sp.render(variant=None, collection=None)
        assert "Block: None" in result


class TestSharedBlock:
    def test_clean_rejects_non_shared_block(self):
        from phoxtail.streams.models import SharedBlock

        block = BlockFactory(is_shared=False)
        sb = SharedBlock(block=block)
        with pytest.raises(ValidationError) as exc_info:
            sb.clean()
        assert "block" in exc_info.value.message_dict
