"""The authorization server's URL surface.

django-oauth-toolkit reverses its own views under the ``oauth2_provider``
namespace, so this module carries that name rather than the app's. The
discovery document is mounted at the root — ``/.well-known/…`` is the only
address a client can compute from the site's name — and the working
endpoints under ``o/``.

Only the authorization server's own document is published. The library
also ships a protected-resource document (RFC 9728) for the site itself,
and it would answer today with the library's placeholder scopes; whether
the API is declared a resource, and with what, is a decision not yet taken,
so that document is not served.
"""

from django.urls import include, path
from oauth2_provider.urls import base_urlpatterns, metadata_urlpatterns

app_name = "oauth2_provider"

urlpatterns = [
    *[route for route in metadata_urlpatterns if route.name.startswith("oauth-server-metadata")],
    path("o/", include(base_urlpatterns)),
]
