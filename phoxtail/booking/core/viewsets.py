from django.urls import path
from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from .admin.settings.views import admin_settings_index_view
from .models import BookingGroup, Location, Space, Staff
from .permissions import BookingViewSet


class BookingSettingsViewSet(BookingViewSet):
    name = "booking_settings"
    menu_label = _("Settings")
    icon = "settings"
    menu_order = 400
    required_permissions = ["access_booking_settings"]

    def get_urlpatterns(self):
        return [
            path("", admin_settings_index_view, name="index"),
        ]


class LocationViewSet(SnippetViewSet):
    model = Location
    icon = "site"
    menu_label = _("Locations")
    menu_name = _("Locations")
    menu_order = 100
    list_display = ["name", "city", "country", "is_active"]


class SpaceViewSet(SnippetViewSet):
    model = Space
    icon = "home"
    menu_label = _("Spaces")
    menu_name = _("Spaces")
    menu_order = 200
    list_display = ["name", "location", "capacity", "is_active"]


class StaffViewSet(SnippetViewSet):
    model = Staff
    icon = "groups"
    menu_label = _("Staff")
    menu_name = _("Staff")
    menu_order = 300
    list_display = ["user", "bio"]


class BookingGroupViewSet(SnippetViewSet):
    model = BookingGroup
    icon = "lock"
    menu_label = _("Groups")
    menu_name = _("Groups")
    menu_order = 350
    list_display = ["name", "is_active"]
