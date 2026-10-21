"""URLConf for the sync page's tests: Wagtail's admin (which mounts the sync
and Remotes views) and core's modal, which the shared test ROOT_URLCONF does
not mount."""

from django.urls import include, path
from wagtail.admin import urls as wagtailadmin_urls

urlpatterns = [
    path("admin/", include(wagtailadmin_urls)),
    path("core/", include("phoxtail.core.urls")),
]
