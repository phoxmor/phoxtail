from functools import cached_property
from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from wagtail.admin.ui.tables import Column, TitleColumn
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail.snippets.views.chooser import (
    ChooseResultsView,
    ChooseView,
)
from wagtail.snippets.views.chooser import (
    SnippetChooserViewSet as BaseSnippetChooserViewSet,
)
from wagtail.snippets.widgets import AdminSnippetChooser

from phoxtail.core.views import MultiSelectChipsSearchView, SingleSelectSearchView

from .constants import WORKFLOW_CHOICES
from .forms import StudioContextForm
from .models import Block, BlockVariant
from .permissions import StreamsPermissionMixin, streams_permission_required


class BlockVariantChooseView(ChooseView):
    def filter_object_list(self, objects):
        objects = super().filter_object_list(objects)
        block_identifier = self.request.GET.get("block_identifier")
        if block_identifier:
            try:
                block = Block.objects.get(identifier=block_identifier)
            except Block.DoesNotExist:
                return BlockVariant.objects.none()
            if hasattr(objects, "filter"):
                objects = objects.filter(block=block)
            else:
                matching_ids = [obj.pk for obj in objects if obj.block_id == block.pk]
                objects = BlockVariant.objects.filter(pk__in=matching_ids)
        return objects

    @property
    def title_column(self):
        return TitleColumn(
            "name",
            label="Variant Name",
            accessor="name",
            id_accessor="pk",
            url_name=self.chosen_url_name,
            link_attrs={"data-chooser-modal-choice": True},
        )

    @property
    def columns(self):
        columns = super().columns
        columns.append(
            Column(
                "collection",
                label="Collection",
                accessor=lambda obj: obj.collection.name if obj.collection else "",
            )
        )
        columns.append(
            Column(
                "preview",
                label="Preview",
                accessor=lambda obj: mark_safe(
                    f'<img src="{obj.preview_image.file.url}" alt="Preview" '
                    f'style="max-width: 150px; height: auto; border-radius: 4px;" />'
                    if obj.preview_image
                    else '<span style="color: #999;">No preview</span>'
                ),
            )
        )
        return columns


class BlockVariantChooseResultsView(ChooseResultsView):
    def filter_object_list(self, objects):
        objects = super().filter_object_list(objects)
        block_identifier = self.request.GET.get("block_identifier")
        if block_identifier:
            try:
                block = Block.objects.get(identifier=block_identifier)
            except Block.DoesNotExist:
                return BlockVariant.objects.none()
            if hasattr(objects, "filter"):
                objects = objects.filter(block=block)
            else:
                matching_ids = [obj.pk for obj in objects if obj.block_id == block.pk]
                objects = BlockVariant.objects.filter(pk__in=matching_ids)
        return objects

    @property
    def title_column(self):
        return TitleColumn(
            "name",
            label="Variant Name",
            accessor="name",
            id_accessor="pk",
            url_name=self.chosen_url_name,
            link_attrs={"data-chooser-modal-choice": True},
        )

    @property
    def columns(self):
        columns = super().columns
        columns.append(
            Column(
                "collection",
                label="Collection",
                accessor=lambda obj: obj.collection.name if obj.collection else "",
            )
        )
        columns.append(
            Column(
                "preview",
                label="Preview",
                accessor=lambda obj: mark_safe(
                    f'<img src="{obj.preview_image.file.url}" alt="Preview" '
                    f'style="max-width: 150px; height: auto; border-radius: 4px;" />'
                    if obj.preview_image
                    else '<span style="color: #999;">No preview</span>'
                ),
            )
        )
        return columns


class BlockVariantChooserViewSet(BaseSnippetChooserViewSet):
    model = BlockVariant
    choose_view_class = BlockVariantChooseView
    choose_results_view_class = BlockVariantChooseResultsView
    preserve_url_parameters = ["multiple", "block_identifier"]


class SharedBlockChooseView(ChooseView):
    def get_object_list(self):
        return Block.objects.filter(is_shared=True)


class SharedBlockChooseResultsView(ChooseResultsView):
    def get_object_list(self):
        return Block.objects.filter(is_shared=True)


class SharedBlockChooserViewSet(BaseSnippetChooserViewSet):
    model = Block
    icon = "widgets"
    choose_view_class = SharedBlockChooseView
    choose_results_view_class = SharedBlockChooseResultsView


class SharedBlockChooserWidget(AdminSnippetChooser):
    def __init__(self, **kwargs):
        super().__init__(Block, icon="widgets", **kwargs)

    def get_chooser_modal_url(self):
        return reverse("shared_block_chooser:choose")


class BlockVariantChooserWidget(AdminSnippetChooser):
    def __init__(self, model, block_identifier=None, **kwargs):
        self.block_identifier = block_identifier
        super().__init__(model, **kwargs)

    def get_chooser_modal_url(self):
        url = super().get_chooser_modal_url()
        if self.block_identifier:
            separator = "&" if "?" in url else "?"
            params = urlencode({"block_identifier": self.block_identifier})
            url = f"{url}{separator}{params}"
        return url


class BlockVariantChooserBlock(SnippetChooserBlock):
    def __init__(self, block_identifier=None, **kwargs):
        self.block_identifier = block_identifier
        super().__init__("phoxtail_streams.BlockVariant", **kwargs)

    @cached_property
    def widget(self):
        icon = self.target_model.snippet_viewset.icon
        return BlockVariantChooserWidget(
            model=self.target_model,
            block_identifier=self.block_identifier,
            icon=icon,
        )


def _get_studio_form(request):
    workflow = request.GET.get("workflow", WORKFLOW_CHOICES.CREATE)
    form_fields = ("system_prompt", "block", "variant", "collection", "references")
    has_form_data = any(request.GET.get(k) for k in form_fields)
    if has_form_data:
        return StudioContextForm(request.GET)
    else:
        return StudioContextForm(initial={"workflow": workflow})


@streams_permission_required("access_stream_studio")
def studio_index_view(request):
    form = _get_studio_form(request)
    rendered_prompt = form.get_rendered_prompt() if form.is_bound else None
    return render(
        request,
        "phoxtail_streams/studio/index.html",
        {"form": form, "rendered_prompt": rendered_prompt},
    )


@streams_permission_required("access_stream_studio")
def studio_context_modal_view(request):
    form = _get_studio_form(request)
    return render(
        request,
        "phoxtail_streams/studio/partials/forms/context/modal.html",
        {"form": form},
    )


@streams_permission_required("access_stream_studio")
def studio_apply_context_view(request):
    form = _get_studio_form(request)
    rendered_prompt = form.get_rendered_prompt() if form.is_bound else None
    return render(
        request,
        "phoxtail_streams/studio/partials/forms/context/response.html",
        {"form": form, "rendered_prompt": rendered_prompt},
    )


def _studio_form_state_context(form):
    return {
        "workflow_value": form["workflow"].value(),
        "system_prompt_value": form["system_prompt"].value(),
        "block_value": form["block"].value(),
        "collection_value": form["collection"].value(),
        "variant_value": form["variant"].value(),
        "rendered_prompt": (form.get_rendered_prompt() if form.is_bound else None),
    }


class _StudioSingleSelectBase(StreamsPermissionMixin, SingleSelectSearchView):
    required_permissions = ["access_stream_studio"]
    form_class = StudioContextForm
    hx_include = "#context-parent-fields, #references-selected-values"

    def get_extra_context(self, form):
        return _studio_form_state_context(form)


class StudioSearchSystemPromptView(_StudioSingleSelectBase):
    field_name = "system_prompt"
    search_url_name = "studio:search_system_prompt"
    oob_response_template = (
        "phoxtail_streams/studio/partials/forms/"
        "widgets/system_prompt_search_response.html"
    )


class StudioSearchBlockView(_StudioSingleSelectBase):
    field_name = "block"
    search_url_name = "studio:search_block"
    oob_response_template = (
        "phoxtail_streams/studio/partials/forms/widgets/block_search_response.html"
    )


class StudioSearchCollectionView(_StudioSingleSelectBase):
    field_name = "collection"
    search_url_name = "studio:search_collection"
    oob_response_template = (
        "phoxtail_streams/studio/partials/forms/widgets/collection_search_response.html"
    )

    def get_extra_context(self, form):
        return {
            **_studio_form_state_context(form),
            "references_field": form["references"],
            "references_hx_include": (
                "#context-parent-fields, #references-selected-values"
            ),
            "references_item_template": (
                "phoxtail_streams/studio/partials/"
                "forms/widgets/"
                "reference_item_display.html"
            ),
        }


class StudioSearchVariantView(_StudioSingleSelectBase):
    field_name = "variant"
    search_url_name = "studio:search_variant"
    oob_response_template = (
        "phoxtail_streams/studio/partials/forms/widgets/variant_search_response.html"
    )

    def get_extra_context(self, form):
        return {
            **_studio_form_state_context(form),
            "references_field": form["references"],
            "references_hx_include": (
                "#context-parent-fields, #references-selected-values"
            ),
            "references_item_template": (
                "phoxtail_streams/studio/partials/"
                "forms/widgets/"
                "reference_item_display.html"
            ),
        }


class StudioSearchReferencesView(StreamsPermissionMixin, MultiSelectChipsSearchView):
    required_permissions = ["access_stream_studio"]
    form_class = StudioContextForm
    field_name = "references"
    search_url_name = "studio:search_references"
    widget_id = "references"
    item_template = (
        "phoxtail_streams/studio/partials/forms/widgets/reference_item_display.html"
    )
    hx_include = "#context-parent-fields, #references-selected-values"
    oob_response_template = (
        "phoxtail_streams/studio/partials/forms/widgets/references_search_response.html"
    )

    def get_selected_items_queryset(self, model):
        return model.objects.select_related("block", "collection")

    def get_extra_context(self, form):
        return _studio_form_state_context(form)
