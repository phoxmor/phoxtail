from functools import cached_property
from urllib.parse import urlencode

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

from .models import Block, BlockVariant


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
                    f'<img src="{obj.preview_image_desktop.file.url}" alt="Preview" '
                    f'style="max-width: 150px; height: auto; border-radius: 4px;" />'
                    if obj.preview_image_desktop
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
                    f'<img src="{obj.preview_image_desktop.file.url}" alt="Preview" '
                    f'style="max-width: 150px; height: auto; border-radius: 4px;" />'
                    if obj.preview_image_desktop
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
