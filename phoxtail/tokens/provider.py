"""What the authorization server is told about itself.

The library ships the server; this module is phoxtail's part of its
configuration — the values every site must agree on for a remote client to
find its way in and be refused what the standards say to refuse. The app
declares them as defaults, and the system checks hold the line when a
project's own ``OAUTH2_PROVIDER`` displaces them.
"""

from phoxtail.cli.utils.config import get_public_site_url

# Three things the library still accepts for the sake of old deployments,
# and advertises on the discovery card: the implicit grant (token in a URL
# fragment), the password grant (the client sees the password) and a
# "plain" PKCE challenge (the challenge is the verifier). A new site has
# nothing to keep compatible, so none is offered from the first day.
REFUSED_FROM_THE_FIRST_DAY = (
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT",
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT",
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD",
)


def issuer() -> str:
    """The authorization server's own name, as advertised to strangers.

    The MCP server's protected-resource document names this site as its
    authorization server, serialised by the protocol library as a root URL
    with a trailing slash. A client then holds that string and compares it,
    character for character, against the ``issuer`` this site publishes —
    so the two must come from the same resolver, never from a value typed
    into a settings file where it would drift.
    """
    return get_public_site_url() + "/"


def defaults() -> dict:
    """``OAUTH2_PROVIDER`` as phoxtail ships it.

    Evaluated when the settings module imports the app — the same moment
    every other setting takes its value, from the same working directory
    (``phoxtail.toml`` is found by walking up from it, and in production
    ``DOMAIN`` makes the directory irrelevant).
    """
    return {
        "OIDC_ISS_ENDPOINT": issuer(),
        **{gate: True for gate in REFUSED_FROM_THE_FIRST_DAY},
    }
