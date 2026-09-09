"""Framework-free token authentication.

This module has no Ninja / DRF / framework imports. If Phoxtail migrates
away from Ninja the adapter in `ninja.py` is the only file that needs to
change; this core remains.
"""

import hashlib
from datetime import timedelta

from django.utils import timezone

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
