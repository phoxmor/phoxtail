from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.admin.panels.group import ObjectList, TabbedInterface
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail_color_panel.edit_handlers import NativeColorPanel

from .models import FontFamily, FontRole, FontWeight, Palette, PaletteRole, PaletteSet
from .views import PaletteChooserViewSet


class PaletteRoleViewSet(SnippetViewSet):
    model = PaletteRole
    icon = "sell"
    menu_label = _("Palette Roles")
    menu_name = _("Palette Roles")
    menu_order = 150
    list_display = ["name", "identifier"]
    list_filter: list[str] = []
    search_fields = ["name", "identifier"]

    panels = [
        FieldPanel("name"),
        FieldPanel("identifier"),
        FieldPanel("description"),
    ]


class FontRoleViewSet(SnippetViewSet):
    model = FontRole
    icon = "sell"
    menu_label = _("Font Roles")
    menu_name = _("Font Roles")
    menu_order = 150
    list_display = ["name", "identifier"]
    list_filter: list[str] = []
    search_fields = ["name", "identifier"]

    panels = [
        FieldPanel("name"),
        FieldPanel("identifier"),
        FieldPanel("description"),
    ]


class FontFamilyViewSet(SnippetViewSet):
    model = FontFamily
    icon = "brand-family"
    menu_label = _("Font Families")
    menu_name = _("Font Families")
    menu_order = 100
    list_display = ["name", "category"]
    list_filter = ["category"]
    search_fields = ["name", "description"]

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("name"),
                    FieldPanel("category"),
                    FieldPanel("fallback"),
                    FieldPanel("description"),
                ],
                heading=_("Details"),
            ),
            ObjectList(
                [
                    InlinePanel("weights", label=_("Font Weight")),
                ],
                heading=_("Weights"),
            ),
        ]
    )


class FontWeightViewSet(SnippetViewSet):
    model = FontWeight
    icon = "match-case"
    menu_label = _("Font Weights")
    menu_name = _("Font Weights")
    menu_order = 110
    list_display = ["family", "weight", "style"]
    list_filter = ["family", "style"]


class PaletteSetViewSet(SnippetViewSet):
    model = PaletteSet
    icon = "style"
    menu_label = _("Palette Sets")
    menu_name = _("Palette Sets")
    menu_order = 190
    list_display = ["name", "identifier"]
    list_filter: list[str] = []
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
                    InlinePanel(
                        "palettes",
                        label=_("Palette"),
                        panels=[
                            FieldPanel("title"),
                            FieldPanel("description"),
                            NativeColorPanel("shade_50"),
                            NativeColorPanel("shade_100"),
                            NativeColorPanel("shade_200"),
                            NativeColorPanel("shade_300"),
                            NativeColorPanel("shade_400"),
                            NativeColorPanel("shade_500"),
                            NativeColorPanel("shade_600"),
                            NativeColorPanel("shade_700"),
                            NativeColorPanel("shade_800"),
                            NativeColorPanel("shade_900"),
                            NativeColorPanel("shade_950"),
                        ],
                    ),
                ],
                heading=_("Palettes"),
            ),
        ]
    )


class PaletteViewSet(SnippetViewSet):
    model = Palette
    icon = "palette"
    menu_label = _("Palettes")
    menu_name = _("Palettes")
    menu_order = 200
    list_display = ["title", "palette_set", "shades_preview"]
    list_filter = ["palette_set"]
    search_fields = ["title", "description"]
    chooser_viewset_class = PaletteChooserViewSet

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("palette_set"),
                    FieldPanel("title"),
                    FieldPanel("description"),
                ],
                heading=_("Details"),
            ),
            ObjectList(
                [
                    NativeColorPanel("shade_50"),
                    NativeColorPanel("shade_100"),
                    NativeColorPanel("shade_200"),
                    NativeColorPanel("shade_300"),
                    NativeColorPanel("shade_400"),
                    NativeColorPanel("shade_500"),
                    NativeColorPanel("shade_600"),
                    NativeColorPanel("shade_700"),
                    NativeColorPanel("shade_800"),
                    NativeColorPanel("shade_900"),
                    NativeColorPanel("shade_950"),
                ],
                heading=_("Shades"),
            ),
        ]
    )
