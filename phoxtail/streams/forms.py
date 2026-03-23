from django import forms
from django.utils.translation import gettext_lazy as _

from phoxtail.core.fields import MultiSelectChipsField, SingleSelectSearchField

from .constants import WORKFLOW_CHOICES
from .models import Block, BlockSystemPrompt, BlockVariant, VariantCollection


class StudioContextForm(forms.Form):
    workflow = forms.ChoiceField(
        choices=WORKFLOW_CHOICES.choices,
        initial=WORKFLOW_CHOICES.CREATE,
        widget=forms.HiddenInput(),
        required=True,
    )

    system_prompt = SingleSelectSearchField(
        queryset=BlockSystemPrompt.objects.none(),
        required=True,
        label=_("System Prompt"),
        help_text=_("AI prompt template"),
    )

    block = SingleSelectSearchField(
        queryset=Block.objects.all(),
        required=False,
        label=_("Block"),
        help_text=_("The block type to create a variant for"),
    )

    variant = SingleSelectSearchField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        required=False,
        label=_("Variant"),
        help_text=_("The existing variant to refine or enhance"),
    )

    collection = SingleSelectSearchField(
        queryset=VariantCollection.objects.all(),
        required=False,
        label=_("Collection"),
        help_text=_("Design system to follow"),
    )

    references = MultiSelectChipsField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("References"),
        help_text=_(
            "Select existing variants to use as design inspiration. "
            "Filtered to show only variants from the selected collection."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workflow = self._get_workflow()
        self._configure_for_workflow(workflow)
        self._set_references_queryset(workflow)

    def _configure_for_workflow(self, workflow):
        self._set_system_prompt_queryset(workflow)
        if workflow == WORKFLOW_CHOICES.CREATE:
            self.fields["block"].required = True
            self.fields["variant"].required = False
            self.fields["collection"].required = True
        else:
            self.fields["block"].required = False
            self.fields["variant"].required = True
            self.fields["collection"].required = False

    def _get_workflow(self):
        if self.is_bound and self.data.get("workflow"):
            return self.data.get("workflow")
        return self.initial.get("workflow", WORKFLOW_CHOICES.CREATE)

    def _set_system_prompt_queryset(self, workflow):
        if workflow == WORKFLOW_CHOICES.EDIT:
            self.fields["system_prompt"].queryset = BlockSystemPrompt.objects.filter(
                _requires_variant=True
            )
        else:
            self.fields["system_prompt"].queryset = BlockSystemPrompt.objects.filter(
                _requires_variant=False
            )

    def _set_references_queryset(self, workflow):
        collection = None
        variant_to_exclude = None

        if workflow == WORKFLOW_CHOICES.CREATE:
            if self.is_bound:
                collection_id = self.data.get("collection")
                if collection_id:
                    try:
                        collection = VariantCollection.objects.get(pk=collection_id)
                    except VariantCollection.DoesNotExist:
                        pass
        else:
            if self.is_bound:
                variant_id = self.data.get("variant")
                if variant_id:
                    try:
                        variant = BlockVariant.objects.select_related(
                            "block", "collection"
                        ).get(pk=variant_id)
                        collection = variant.collection
                        variant_to_exclude = variant.pk
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

        if self.is_bound:
            submitted_refs = self.data.getlist("references")
            if submitted_refs:
                valid_pks = set(str(pk) for pk in queryset.values_list("pk", flat=True))
                sanitized = [r for r in submitted_refs if r in valid_pks]
                if len(sanitized) != len(submitted_refs):
                    data = self.data.copy()
                    data.setlist("references", sanitized)
                    self.data = data

    def clean(self):
        cleaned_data = super().clean()
        workflow = cleaned_data.get("workflow")

        if workflow == WORKFLOW_CHOICES.CREATE:
            cleaned_data["variant"] = None
        elif workflow == WORKFLOW_CHOICES.EDIT:
            cleaned_data["block"] = None
            cleaned_data["collection"] = None

        return cleaned_data

    def get_rendered_prompt(self):
        if not self.is_valid():
            return None

        system_prompt = self.cleaned_data.get("system_prompt")
        workflow = self.cleaned_data.get("workflow")
        references = self.cleaned_data.get("references", [])

        if workflow == WORKFLOW_CHOICES.CREATE:
            block = self.cleaned_data.get("block")
            collection = self.cleaned_data.get("collection")
            variant = None
        else:
            variant = self.cleaned_data.get("variant")
            block = variant.block if variant else None
            collection = variant.collection if variant else None

        if not (system_prompt and block and collection):
            return None

        return system_prompt.render(
            block=block,
            collection=collection,
            variant=variant,
            references=list(references) if references else [],
        )
