"""What the authorization server is told about itself.

The library ships the server; this module is phoxtail's part of its
configuration — the values every site must agree on for a remote client to
find its way in and be refused what the standards say to refuse. The app
declares them as defaults, and the system checks hold the line when a
project's own ``OAUTH2_PROVIDER`` displaces them.
"""

from phoxtail.cli.utils.config import get_public_site_url

# Five things the library still tolerates for the sake of old deployments.
# Three it accepts and advertises on the discovery card: the implicit grant
# (token in a URL fragment), the password grant (the client sees the
# password) and a "plain" PKCE challenge (the challenge is the verifier).
# One it omits: the ``iss`` parameter on the authorization response, which
# is how a client talking to more than one authorization server knows
# which of them sent a given code. One it does at rest: storing access and
# refresh tokens in cleartext, where a backup or a dump hands out working
# keys — phoxtail's own tokens have only ever been stored as digests. A new
# site has nothing to keep compatible, so none of the five is tolerated
# from the first day.
REFUSED_FROM_THE_FIRST_DAY = (
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT",
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT",
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD",
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS",
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE",
)


SCOPES_BACKEND = "phoxtail.tokens.bundles.Bundles"
VALIDATOR = "phoxtail.tokens.bundles.Validator"
AUDIENCE = "phoxtail.tokens.audience.names_this_server"


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
        # The scopes an outside client may ask for are phoxtail's bundles,
        # derived from the doors — never the library's placeholder pair,
        # and never a codename, which is internal and mutable.
        "SCOPES_BACKEND_CLASS": SCOPES_BACKEND,
        # And a request that names no scope is refused as invalid_scope
        # rather than shown to a person as a request for nothing.
        "OAUTH2_VALIDATOR_CLASS": VALIDATOR,
        # A key names the server it was minted for, and the API stands
        # behind that server rather than being it: the library's own
        # check compares the request's address and would refuse every
        # such key; ours asks whether the key names this project's door.
        "RESOURCE_SERVER_TOKEN_RESOURCE_VALIDATOR": AUDIENCE,
        # A phone app or a CLI cannot keep a secret — every copy is the same
        # binary — so it authenticates at the token endpoint with none and
        # proves itself with PKCE instead. The library accepts that; the
        # card must say so, or a client reading it cannot tell it may
        # register as public.
        "OAUTH2_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED": [
            "none",
            "client_secret_basic",
            "client_secret_post",
        ],
        # A CLI client listens for its callback on a port it picks at run
        # time. RFC 8252 exempts loopback addresses from exact port matching;
        # the library extends that to the name "localhost" only on request,
        # and that is the name such clients use.
        "ALLOW_LOCALHOST_LOOPBACK": True,
        # The key shown on every call is worth an hour to whoever steals it;
        # the key that mints keys is shown only to this server and is worth
        # a week — and every use issues a fresh one, so a client used at
        # least weekly is never sent back to a login screen. Presenting a
        # retired refresh token again means someone holds a copy, and the
        # whole family is revoked rather than guess which.
        #
        # No grace period. The library offers one so a client that never
        # received the rotated answer can retry with the retired token, but
        # its grace path hands back the previous access token's stored
        # value — blank, now that tokens are hashed at rest — and answers
        # 500 instead of a pair. Hashing wins; the retry ends in a login.
        "ACCESS_TOKEN_EXPIRE_SECONDS": 60 * 60,
        "REFRESH_TOKEN_EXPIRE_SECONDS": 7 * 24 * 60 * 60,
        "ROTATE_REFRESH_TOKEN": True,
        "REFRESH_TOKEN_REUSE_PROTECTION": True,
        "REFRESH_TOKEN_GRACE_PERIOD_SECONDS": 0,
    }
