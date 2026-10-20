"""URLConf for the Remotes admin tests: {% url %} needs the view's own
namespace, core's modal and Wagtail's admin, which the shared test
ROOT_URLCONF does not mount."""

from django.urls import include, path
from wagtail.admin import urls as wagtailadmin_urls

from phoxtail.remotes.admin.remotes.viewsets import RemotesViewSet

urlpatterns = [
    path("admin/remotes/", include((RemotesViewSet().get_urlpatterns(), "remotes"))),
    path("admin/", include(wagtailadmin_urls)),
    path("core/", include("phoxtail.core.urls")),
]
