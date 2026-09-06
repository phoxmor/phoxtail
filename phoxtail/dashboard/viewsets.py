from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.snippets.views.snippets import SnippetViewSet

from phoxtail.dashboard.models import Menu


class MenuViewSet(SnippetViewSet):
    model = Menu
    icon = "menu"
    menu_label = _("Menu")
    menu_name = _("Menu")
    menu_order = 100
    list_display = ["site", "locale", "updated_at"]
    list_filter = ["site", "locale"]
    # A menu has no title of its own to search — site and locale are the only
    # things that tell two of them apart, and both are filters already.
    search_fields: list[str] = []

    panels = [
        FieldPanel("site"),
        FieldPanel("locale"),
        FieldPanel("items"),
    ]
