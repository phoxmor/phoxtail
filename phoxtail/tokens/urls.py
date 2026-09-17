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
from oauth2_provider.urls import base_urlpatterns, dcr_urlpatterns, metadata_urlpatterns

from phoxtail.tokens.views import ConsentView

app_name = "oauth2_provider"

# The consent screen is phoxtail's: the library's route is left out and
# ours takes its name, so the discovery document still reverses it.
endpoints = [
    path("authorize/", ConsentView.as_view(), name="authorize"),
    *[route for route in base_urlpatterns if route.name != "authorize"],
    # Where a client introduces itself by request, and reads or updates
    # what it said; shipped apart from the working endpoints.
    *dcr_urlpatterns,
]

urlpatterns = [
    *[route for route in metadata_urlpatterns if route.name.startswith("oauth-server-metadata")],
    path("o/", include(endpoints)),
]
