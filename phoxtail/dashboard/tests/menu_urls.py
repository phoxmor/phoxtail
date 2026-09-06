"""A URLconf with Wagtail's page routes.

Page.get_url reverses ``wagtail_serve``, and a draft entry reverses
``wagtailadmin_pages:view_draft`` — without both, every page entry reduces
to None and the tests would pass by saying nothing.
"""

from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls

urlpatterns = [
    path("admin/", include(wagtailadmin_urls)),
    path("", include(wagtail_urls)),
]
