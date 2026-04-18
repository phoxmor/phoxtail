from django.urls import path
from django.utils.translation import gettext_lazy as _

from ..permissions import AccessTokensViewSet
from .views import (
    admin_token_create_form_view,
    admin_token_create_view,
    admin_token_detail_form_view,
    admin_token_revoke_form_view,
    admin_token_revoke_view,
    admin_tokens_filters_form_view,
    admin_tokens_filters_view,
    admin_tokens_list_view,
    admin_tokens_search_view,
)


class AccessTokensManagementViewSet(AccessTokensViewSet):
    name = "access_tokens_management"
    menu_label = _("Access Tokens")
    icon = "fingerprint"
    menu_order = 500
    add_to_admin_menu = True
    required_permissions = ["access_tokens_management"]

    def get_urlpatterns(self):
        return [
            path("", admin_tokens_list_view, name="index"),
            path(
                "create-form/",
                admin_token_create_form_view,
                name="admin_token_create_form",
            ),
            path(
                "create/",
                admin_token_create_view,
                name="admin_token_create",
            ),
            path(
                "<uuid:token_id>/detail-form/",
                admin_token_detail_form_view,
                name="admin_token_detail_form",
            ),
            path(
                "<uuid:token_id>/revoke-form/",
                admin_token_revoke_form_view,
                name="admin_token_revoke_form",
            ),
            path(
                "<uuid:token_id>/revoke/",
                admin_token_revoke_view,
                name="admin_token_revoke",
            ),
            path(
                "filters-form/",
                admin_tokens_filters_form_view,
                name="admin_tokens_filters_form",
            ),
            path(
                "filters/",
                admin_tokens_filters_view,
                name="admin_tokens_filters",
            ),
            path(
                "search/",
                admin_tokens_search_view,
                name="admin_tokens_search",
            ),
        ]
