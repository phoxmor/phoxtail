from django.urls import path
from django.utils.translation import gettext_lazy as _

from phoxtail.booking.core.permissions import BookingViewSet

from .views import (
    admin_user_create_form_view,
    admin_user_create_view,
    admin_user_update_form_view,
    admin_users_filters_form_view,
    admin_users_filters_view,
    admin_users_list_view,
    admin_users_search_view,
)


class UsersManagementViewSet(BookingViewSet):
    name = "users_management"
    menu_label = _("Users")
    icon = "groups"
    menu_order = 100
    required_permissions = ["access_users_management"]

    def get_urlpatterns(self):
        return [
            path("", admin_users_list_view, name="index"),
            path(
                "admin-user-update-form/<uuid:user_id>/",
                admin_user_update_form_view,
                name="admin_user_update_form",
            ),
            path(
                "admin-user-create-form/",
                admin_user_create_form_view,
                name="admin_user_create_form",
            ),
            path(
                "admin-user-create-action/",
                admin_user_create_view,
                name="admin_user_create",
            ),
            path(
                "users-filters-form/",
                admin_users_filters_form_view,
                name="admin_users_filters_form",
            ),
            path(
                "users-filters/",
                admin_users_filters_view,
                name="admin_users_filters",
            ),
            path(
                "users-search/",
                admin_users_search_view,
                name="admin_users_search",
            ),
        ]
