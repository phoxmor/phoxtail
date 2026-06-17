from django.urls import path
from django.utils.translation import gettext_lazy as _

from phoxtail.remotes.permissions import RemotesPermissionedViewSet

from .views import (
    admin_remote_add,
    admin_remote_add_form,
    admin_remote_delete,
    admin_remote_delete_form,
    admin_remote_edit,
    admin_remote_edit_form,
    admin_remotes_index,
    admin_remotes_search,
)


class RemotesViewSet(RemotesPermissionedViewSet):
    name = "remotes"
    menu_label = _("Remotes")
    icon = "graph-5"
    menu_order = 601
    add_to_settings_menu = True
    required_permissions = ["manage_remotes"]

    def get_urlpatterns(self):
        return [
            path("", admin_remotes_index, name="index"),
            path("search/", admin_remotes_search, name="search"),
            path("add-form/", admin_remote_add_form, name="add_form"),
            path("add/", admin_remote_add, name="add"),
            path("<int:remote_id>/delete-form/", admin_remote_delete_form, name="delete_form"),
            path("<int:remote_id>/delete/", admin_remote_delete, name="delete"),
            path("<int:remote_id>/edit-form/", admin_remote_edit_form, name="edit_form"),
            path("<int:remote_id>/edit/", admin_remote_edit, name="edit"),
        ]
