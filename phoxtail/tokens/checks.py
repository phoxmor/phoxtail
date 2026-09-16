"""System checks for the authorization server's posture.

``OAUTH2_PROVIDER`` arrives as this app's default settings and is applied
with ``setdefault`` on the whole dict — so a project that defines the dict
for any reason of its own silently replaces every key in it, the issuer and
the gates included. These checks are what turns that silence into an error
at startup and in ``manage.py check --deploy``.
"""

from django.conf import settings
from django.core.checks import Error, register

from phoxtail.tokens.provider import REFUSED_FROM_THE_FIRST_DAY


@register()
def authorization_server_posture(app_configs, **kwargs):
    """Was the app's own declaration displaced?

    Compared against what the app declared, not against a fresh
    computation: both would be computed in this same process, so they
    could only ever agree, and the question worth asking is whether a
    project's settings replaced the dict the app shipped.
    """
    from phoxtail.tokens.apps import PhoxtailTokensConfig

    declared = getattr(settings, "OAUTH2_PROVIDER", {})
    errors = []
    expected = PhoxtailTokensConfig.default_settings["OAUTH2_PROVIDER"]["OIDC_ISS_ENDPOINT"]
    if declared.get("OIDC_ISS_ENDPOINT") != expected:
        errors.append(
            Error(
                f"OAUTH2_PROVIDER['OIDC_ISS_ENDPOINT'] must be {expected!r}, the name the MCP "
                "server advertises for this site; a client compares the two as plain strings.",
                hint="Do not define OAUTH2_PROVIDER wholesale; extend phoxtail.tokens' defaults.",
                id="phoxtail_tokens.E001",
            )
        )
    for gate in REFUSED_FROM_THE_FIRST_DAY:
        if not declared.get(gate):
            errors.append(
                Error(
                    f"OAUTH2_PROVIDER[{gate!r}] is off: the site would accept and advertise a "
                    "grant or challenge that RFC 9700 says not to.",
                    id="phoxtail_tokens.E002",
                )
            )
    return errors
