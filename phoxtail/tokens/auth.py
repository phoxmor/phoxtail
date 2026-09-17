"""Framework-free token authentication.

This module has no Ninja / DRF / framework imports. If Phoxtail migrates
away from Ninja the adapter in `ninja.py` is the only file that needs to
change; this core remains.

Two kinds of key arrive at the same door. Phoxtail's own, minted here and
found by digest in this app's table; and the authorization server's,
minted after a person's consent and found by the same digest in that
server's table. Each is read into one :class:`Credential`, with its
stored names expanded to codenames, so nothing after this module knows
which kind it holds.
"""

import hashlib
from datetime import timedelta

from django.utils import timezone

from phoxtail.core.authorization import Credential

# Throttle `last_used_at` updates: every authenticated request would
# otherwise issue a DB UPDATE on the hot path. One update per minute is
# more than enough granularity for "when was this token last used?" while
# keeping read-only requests free of write amplification.
_LAST_USED_THROTTLE = timedelta(seconds=60)


def authenticate(raw_token: str):
    """Return the :class:`AccessToken` for a valid raw token, or ``None``.

    Returns the token rather than its user because the credential is what
    was looked up, and callers need more of it than the owner: scopes,
    type and expiry all live here. ``token.user`` is select_related, so
    reading the owner costs no extra query.

    A token is valid iff:
      - it parses (non-empty, minimum length)
      - a row with its SHA-256 digest exists
      - the row is not revoked
      - the row has not expired
    """
    if not raw_token or len(raw_token) < 8:
        return None

    # Deferred import: keeps this module importable before Django's app
    # registry is ready (e.g. from settings or doctests).
    from .models import AccessToken

    digest = hashlib.sha256(raw_token.encode()).hexdigest()

    try:
        token = AccessToken.objects.select_related("user").get(
            digest=digest,
            revoked_at__isnull=True,
        )
    except AccessToken.DoesNotExist:
        return None

    now = timezone.now()
    if token.expires_at is not None and token.expires_at < now:
        return None

    if token.last_used_at is None or (now - token.last_used_at) > _LAST_USED_THROTTLE:
        # Use .update() rather than .save() to avoid racing with other
        # fields and to skip auto_now hooks we don't have anyway.
        AccessToken.objects.filter(pk=token.pk).update(last_used_at=now)

    return token


def credential(token) -> Credential:
    """Read a phoxtail key's row into the one shape every reader takes."""
    from .bundles import expand

    return Credential(
        names=tuple(token.scopes),
        scopes=expand(token.scopes),
        unrestricted=bool(token.unrestricted),
        expires_at=token.expires_at,
        row=token,
    )


def issued_credential(request) -> Credential | None:
    """Read a key the authorization server issued, or ``None``.

    The server's own validation, asked through its own core: the digest
    lookup, expiry, whether the key was bound to a resource this request
    is not under, and whether its client is still usable — everything the
    library checks today and whatever it adds. It sets ``request.user``
    as a side effect, which the caller of this door ignores: the person is
    carried on the credential, not on the request.

    A key from this server always carries a ceiling. Its names are the
    bundles a person approved, and what they mean is read now, not when
    they were approved.
    """
    from oauth2_provider.oauth2_backends import get_oauthlib_core

    from .bundles import expand

    valid, oauth = get_oauthlib_core().verify_request(request, scopes=[])
    if not valid:
        return None
    token = oauth.access_token
    names = tuple(token.scope.split())
    return Credential(
        names=names,
        scopes=expand(names),
        unrestricted=False,
        expires_at=token.expires,
        row=token,
    )
