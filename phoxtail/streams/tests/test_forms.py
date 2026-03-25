import pytest
from django.http import QueryDict

from phoxtail.streams.forms import StudioContextForm

from .factories import (
    BlockVariantFactory,
    VariantCollectionFactory,
)

pytestmark = pytest.mark.django_db


class TestStudioContextFormUnbound:
    def test_unbound_form_has_empty_references_queryset(self):
        form = StudioContextForm()
        assert form.fields["references"].queryset.count() == 0

    def test_unbound_form_is_not_bound(self):
        form = StudioContextForm()
        assert not form.is_bound


class TestStudioContextFormReferences:
    def test_references_filtered_by_collection(self, variant, collection):
        other_col = VariantCollectionFactory()
        ref_in = BlockVariantFactory(collection=collection)
        BlockVariantFactory(collection=other_col)

        data = QueryDict(mutable=True)
        data["variant"] = str(variant.pk)
        data["collection"] = str(collection.pk)

        form = StudioContextForm(data)
        ref_pks = set(form.fields["references"].queryset.values_list("pk", flat=True))
        assert ref_in.pk in ref_pks
        # The selected variant itself should be excluded
        assert variant.pk not in ref_pks

    def test_references_empty_without_collection(self, variant):
        data = QueryDict(mutable=True)
        data["variant"] = str(variant.pk)

        form = StudioContextForm(data)
        assert form.fields["references"].queryset.count() == 0

    def test_collection_derived_from_variant_when_not_explicit(self, variant):
        # Only variant provided, no collection — should derive collection from variant
        ref = BlockVariantFactory(collection=variant.collection)
        data = QueryDict(mutable=True)
        data["variant"] = str(variant.pk)

        form = StudioContextForm(data)
        ref_pks = set(form.fields["references"].queryset.values_list("pk", flat=True))
        assert ref.pk in ref_pks

    def test_explicit_collection_overrides_variant_collection(self, variant):
        other_col = VariantCollectionFactory()
        ref_other = BlockVariantFactory(collection=other_col)

        data = QueryDict(mutable=True)
        data["variant"] = str(variant.pk)
        data["collection"] = str(other_col.pk)

        form = StudioContextForm(data)
        ref_pks = set(form.fields["references"].queryset.values_list("pk", flat=True))
        assert ref_other.pk in ref_pks

    def test_sanitizes_invalid_reference_pks(self, variant, collection):
        valid_ref = BlockVariantFactory(collection=collection)
        other_ref = BlockVariantFactory()  # different collection

        data = QueryDict(mutable=True)
        data["variant"] = str(variant.pk)
        data["collection"] = str(collection.pk)
        data.setlist("references", [str(valid_ref.pk), str(other_ref.pk)])

        form = StudioContextForm(data)
        submitted = form.data.getlist("references")
        assert str(valid_ref.pk) in submitted
        assert str(other_ref.pk) not in submitted


class TestStudioContextFormRenderedPrompt:
    def test_returns_none_when_invalid(self):
        form = StudioContextForm(QueryDict())
        assert form.get_rendered_prompt() is None

    def test_returns_rendered_string_when_valid(
        self, system_prompt, variant, collection
    ):
        data = QueryDict(mutable=True)
        data["system_prompt"] = str(system_prompt.pk)
        data["variant"] = str(variant.pk)
        data["collection"] = str(collection.pk)

        form = StudioContextForm(data)
        result = form.get_rendered_prompt()
        assert result is not None
        assert variant.block.name in result
        assert collection.name in result

    def test_returns_none_for_unbound_form(self):
        form = StudioContextForm()
        assert form.get_rendered_prompt() is None
