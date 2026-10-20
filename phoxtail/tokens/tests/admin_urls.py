"""URLConf for the API Tokens admin tests: {% url %} needs the view's own
namespace, core's modal and Wagtail's admin, which the shared test
ROOT_URLCONF does not mount."""

from django.urls import include, path
from wagtail.admin import urls as wagtailadmin_urls

from phoxtail.tokens.admin.viewsets import AccessTokensManagementViewSet

urlpatterns = [
    path(
        "admin/tokens/",
        include((AccessTokensManagementViewSet().get_urlpatterns(), "access_tokens_management")),
    ),
    path("admin/", include(wagtailadmin_urls)),
    path("core/", include("phoxtail.core.urls")),
]
