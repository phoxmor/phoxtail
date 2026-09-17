"""A root URLconf shaped like a hatched project's: the API beside every mount.

``discovery_urls`` mounts what the app protocol collects; a project also
mounts the API at ``/api/`` by hand in its own ``urls.py``. A key issued
by the authorization server is spent at the API, so a test of that has
to serve both from one root.
"""

from django.urls import include, path

from phoxtail.core.wiring import collect_url_patterns

urlpatterns = [path("api/", include("phoxtail.api.urls")), *collect_url_patterns()]
