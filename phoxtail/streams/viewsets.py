from django.urls import path
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.admin.panels.group import ObjectList, TabbedInterface
from wagtail.snippets.views.snippets import SnippetViewSet

from .admin.panels import CodeEditorPanel
from .models import (
    Block,
    BlockSystemPrompt,
    BlockVariant,
    SharedBlock,
    VariantCollection,
)
from .permissions import StreamsViewSet
from .views import (
    BlockVariantChooserViewSet,
    StudioSearchBlockView,
    StudioSearchCollectionView,
    StudioSearchReferencesView,
    StudioSearchSystemPromptView,
    StudioSearchVariantView,
    studio_apply_context_view,
    studio_context_modal_view,
    studio_index_view,
)


class BlockViewSet(SnippetViewSet):
    model = Block
    icon = "widgets"
    menu_label = _("Blocks")
    menu_name = _("Blocks")
    menu_order = 100
    list_display = ["name", "identifier", "is_shared"]
    list_filter = ["is_shared"]
    search_fields = ["name", "identifier", "description"]

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("name"),
                    FieldPanel("identifier"),
                    FieldPanel("description"),
                    FieldPanel("icon"),
                    FieldPanel("group"),
                    FieldPanel("is_shared"),
                    FieldPanel("page_types"),
                ],
                heading=_("Details"),
            ),
            ObjectList(
                [
                    FieldPanel("schema"),
                ],
                heading=_("Schema"),
            ),
        ]
    )


class SharedBlockViewSet(SnippetViewSet):
    model = SharedBlock
    icon = "interests"
    menu_label = _("Shared Blocks")
    menu_name = _("Shared Blocks")
    menu_order = 200
    list_display = ["block", "site", "locale"]
    list_filter = ["block", "site", "locale"]
    search_fields = []

    panels = [
        FieldPanel("block"),
        FieldPanel("site"),
        FieldPanel("locale"),
        FieldPanel("content"),
    ]


class BlockVariantViewSet(SnippetViewSet):
    model = BlockVariant
    icon = "category"
    menu_label = _("Variants")
    menu_name = _("Variants")
    menu_order = 300
    list_display = ["name", "block", "collection", "is_default"]
    list_filter = ["block", "collection", "is_default"]
    search_fields = ["name", "identifier", "description"]
    chooser_viewset_class = BlockVariantChooserViewSet

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("block"),
                    FieldPanel("collection"),
                    FieldPanel("name"),
                    FieldPanel("identifier"),
                    FieldPanel("description"),
                    FieldPanel("is_default"),
                    FieldPanel("preview_image"),
                ],
                heading=_("Details"),
            ),
            ObjectList(
                [
                    CodeEditorPanel("html"),
                    CodeEditorPanel("css"),
                    CodeEditorPanel("javascript"),
                ],
                heading=_("Code"),
            ),
        ]
    )


class VariantCollectionViewSet(SnippetViewSet):
    model = VariantCollection
    icon = "graph-5"
    menu_label = _("Collections")
    menu_name = _("Collections")
    menu_order = 400
    list_display = ["name", "identifier"]
    list_filter = []
    search_fields = ["name", "identifier", "description"]

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("name"),
                    FieldPanel("identifier"),
                    FieldPanel("description"),
                ],
                heading=_("Details"),
            ),
            ObjectList(
                [
                    CodeEditorPanel("template"),
                ],
                heading=_("Template"),
            ),
        ]
    )


class BlockSystemPromptViewSet(SnippetViewSet):
    model = BlockSystemPrompt
    icon = "terminal"
    menu_label = _("System Prompts")
    menu_name = _("System Prompts")
    menu_order = 500
    list_display = ["name", "identifier", "updated_at"]
    list_filter = []
    search_fields = ["name", "identifier", "description"]

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("name"),
                    FieldPanel("identifier"),
                    FieldPanel("description"),
                ],
                heading=_("Details"),
            ),
            ObjectList(
                [
                    CodeEditorPanel("template"),
                ],
                heading=_("Template"),
            ),
        ]
    )


class StudioViewSet(StreamsViewSet):
    name = "studio"
    icon = "flowchart"
    menu_label = _("Studio")
    menu_order = 600
    required_permissions = ["access_stream_studio"]

    def get_urlpatterns(self):
        return [
            path("", studio_index_view, name="index"),
            path(
                "context-modal/",
                studio_context_modal_view,
                name="context_modal",
            ),
            path(
                "apply-context/",
                studio_apply_context_view,
                name="apply_context",
            ),
            path(
                "search/system-prompt/",
                StudioSearchSystemPromptView.as_view(),
                name="search_system_prompt",
            ),
            path(
                "search/block/",
                StudioSearchBlockView.as_view(),
                name="search_block",
            ),
            path(
                "search/collection/",
                StudioSearchCollectionView.as_view(),
                name="search_collection",
            ),
            path(
                "search/variant/",
                StudioSearchVariantView.as_view(),
                name="search_variant",
            ),
            path(
                "search/references/",
                StudioSearchReferencesView.as_view(),
                name="search_references",
            ),
        ]
