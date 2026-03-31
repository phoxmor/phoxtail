from django import forms
from django.utils.translation import gettext_lazy as _

from phoxtail.core.fields import MultiSelectChipsField, SingleSelectSearchField

from .models import BlockSystemPrompt, BlockVariant, VariantCollection


class StudioContextForm(forms.Form):
    system_prompt = SingleSelectSearchField(
        queryset=BlockSystemPrompt.objects.all(),
        required=True,
        label=_("System Prompt"),
        help_text=_("AI prompt template"),
    )

    variant = SingleSelectSearchField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        required=True,
        label=_("Variant"),
        help_text=_("The variant to work with (block is derived automatically)"),
    )

    collection = SingleSelectSearchField(
        queryset=VariantCollection.objects.all(),
        required=True,
        label=_("Collection"),
        help_text=_(
            "Design system to follow. Auto-populated from variant, "
            "change to apply a different collection's design direction."
        ),
    )

    references = MultiSelectChipsField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("References"),
        help_text=_(
            "Select existing variants as design inspiration. "
            "Filtered by the selected collection."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_references_queryset()

    def _set_references_queryset(self):
        collection = None
        variant_to_exclude = None

        if self.is_bound:
            collection_id = self.data.get("collection")
            if collection_id:
                try:
                    collection = VariantCollection.objects.get(pk=collection_id)
                except VariantCollection.DoesNotExist:
                    pass

            variant_id = self.data.get("variant")
            if variant_id:
                variant_to_exclude = variant_id
                # Derive collection from variant when not explicitly provided
                if not collection:
                    try:
                        variant = BlockVariant.objects.select_related("collection").get(
                            pk=variant_id
                        )
                        collection = variant.collection
                    except BlockVariant.DoesNotExist:
                        pass

        queryset = BlockVariant.objects.select_related("block", "collection")

        if collection:
            queryset = queryset.filter(collection=collection)
            if variant_to_exclude:
                queryset = queryset.exclude(pk=variant_to_exclude)
        else:
            queryset = BlockVariant.objects.none()

        self.fields["references"].queryset = queryset

        # Sanitize submitted references against current queryset
        if self.is_bound:
            submitted_refs = self.data.getlist("references")
            if submitted_refs:
                valid_pks = set(str(pk) for pk in queryset.values_list("pk", flat=True))
                sanitized = [r for r in submitted_refs if r in valid_pks]
                if len(sanitized) != len(submitted_refs):
                    data = self.data.copy()
                    data.setlist("references", sanitized)
                    self.data = data

    def get_rendered_prompt(self):
        if not self.is_valid():
            return None

        system_prompt = self.cleaned_data.get("system_prompt")
        variant = self.cleaned_data.get("variant")
        collection = self.cleaned_data.get("collection")
        references = self.cleaned_data.get("references", [])

        if not (system_prompt and variant and collection):
            return None

        return system_prompt.render(
            variant=variant,
            collection=collection,
            references=list(references) if references else [],
        )
