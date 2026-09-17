"""The consent screen: the one moment a person decides for an outside client.

The library's authorization view does the whole flow — validates the
request, finds the client, renders, then mints the grant on approval —
and its template lists scope descriptions under the client's own name.
That name is the client's to choose, so it proves nothing. What a person
can actually check is *where* the client is: for a client that
identifies itself by a URL, the host of that URL; and where the code is
about to be delivered, the host of the redirect. This view adds those to
the context and nothing else; the form and the flow are the library's.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from oauth2_provider.cimd import is_cimd_client_id
from oauth2_provider.views import AuthorizationView

LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


def is_loopback(uri: str) -> bool:
    return urlsplit(uri).hostname in LOOPBACK_HOSTS


class ConsentView(AuthorizationView):
    # Named as phoxtail's, not as an override of the library's: the
    # dependency is installed ahead of this app, so the app-directories
    # loader would find the library's copy of a shared name first.
    template_name = "phoxtail_tokens/consent.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = context.get("application")
        if application is None:
            return context
        # A client that registered by metadata document is named by its
        # URL, and the host of that URL is the one fact about it that was
        # fetched rather than declared.
        client_id = application.client_id
        context["client_host"] = urlsplit(client_id).hostname if is_cimd_client_id(client_id) else None
        context["redirect_host"] = urlsplit(context.get("redirect_uri", "")).hostname
        # Every redirect a loopback address means the client is a program
        # on this machine, not a service somewhere: worth a sentence,
        # because the person cannot tell which program from the screen.
        registered = application.redirect_uris.split()
        context["loopback_only"] = bool(registered) and all(is_loopback(uri) for uri in registered)
        return context
