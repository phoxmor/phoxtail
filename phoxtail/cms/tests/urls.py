"""URLconf for the redirect-guard tests.

The shared test settings point ``ROOT_URLCONF`` at ``phoxtail.core.urls``,
which has no ``wagtail_serve`` route. Without it ``Page.get_url_parts()``
cannot reverse a page path, so wagtail's redirect autocreation silently
produces nothing and any test asserting "no redirect was created" passes
whether or not the guard exists. These tests override the urlconf so the
autocreation they are guarding is actually running.
"""

from django.urls import include, path
from wagtail import urls as wagtail_urls

urlpatterns = [
    path("", include(wagtail_urls)),
]
