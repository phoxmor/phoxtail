"""URLconf for tests that run Wagtail's ``describe_collection_contents`` hooks.

The shared test settings point ``ROOT_URLCONF`` at ``phoxtail.core.urls``,
which mounts no Wagtail admin. Every hook registered against that name
builds a ``url`` for its answer by reversing an admin route — "2 images"
links to the images listing — so with no admin mounted the hook raises
``NoReverseMatch`` rather than answering.

That is only ever a test-environment problem: a deployment mounts the
admin. But it means a test asking "is this collection occupied?" would
error instead of answering, and swallowing that error in the endpoint
would be the wrong fix — a hook that cannot answer must not be read as
"empty", or the API would delete a collection the admin refuses to.

So the tests that exercise the hooks override the urlconf and let them run
for real, rather than mocking what Wagtail actually does.
"""

from django.urls import include, path
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.images import urls as wagtailimages_urls

urlpatterns = [
    path("admin/", include(wagtailadmin_urls)),
    path("images/", include(wagtailimages_urls)),
    path("documents/", include(wagtaildocs_urls)),
]
