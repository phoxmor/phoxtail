from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Reservation


class ReservationViewSet(SnippetViewSet):
    model = Reservation
    icon = "event-available"
    menu_label = _("Reservations")
    menu_name = _("Reservations")
    menu_order = 100
    list_display = ["user", "event", "status"]
