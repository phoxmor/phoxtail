from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Service


class ServiceViewSet(SnippetViewSet):
    model = Service
    icon = "view-apps"
    menu_label = _("Services")
    menu_name = _("Services")
    menu_order = 200
    list_display = ["name", "cancellation_lockout_hours", "is_active"]
