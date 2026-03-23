from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from taggit.models import Tag
from wagtail.admin.panels import FieldPanel
from wagtail.models import Locale, Site
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail_color_panel.edit_handlers import NativeColorPanel

from .models import ScheduleItem

User = get_user_model()


class ScheduleItemViewSet(SnippetViewSet):
    model = ScheduleItem
    icon = "date"
    menu_label = _("Schedule Items")
    menu_name = _("Schedule Items")
    menu_order = 400
    list_display = ["title", "description", "locale"]
    list_filter = []
    panels = [
        FieldPanel("title"),
        FieldPanel("description"),
        NativeColorPanel("color"),
    ]


# Register additional snippets
register_snippet(Group)
register_snippet(User)
register_snippet(Site)
register_snippet(Locale)
register_snippet(Tag)
register_snippet(ScheduleItemViewSet)
