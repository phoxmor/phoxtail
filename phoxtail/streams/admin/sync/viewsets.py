from django.urls import path
from django.utils.translation import gettext_lazy as _

from phoxtail.remotes.permissions import RemotesPermissionedViewSet

from .views import (
    admin_sync_index,
    admin_sync_pull,
    admin_sync_push,
    admin_sync_remote_select,
    admin_sync_streams,
    admin_sync_variant_detail,
)


class StreamsSyncViewSet(RemotesPermissionedViewSet):
    name = "streams-sync"
    menu_label = _("Sync")
    icon = "sync"
    menu_order = 900
    required_permissions = ["manage_remotes"]

    def get_urlpatterns(self):
        return [
            path("", admin_sync_index, name="index"),
            path("remote-select/", admin_sync_remote_select, name="remote_select"),
            path("streams/", admin_sync_streams, name="streams"),
            path("pull/", admin_sync_pull, name="pull"),
            path("push/", admin_sync_push, name="push"),
            path("variant-detail/", admin_sync_variant_detail, name="variant_detail"),
        ]
