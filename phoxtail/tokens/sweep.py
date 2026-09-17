"""Remove token rows that can no longer open anything.

Two families of credential live in this database and both leave rows behind:
the authorization server's access and refresh tokens and spent grants, which
its own sweep removes on its own terms, and phoxtail's tokens, one of which
every chat turn mints and revokes. phoxtail's dead rows are kept for
:data:`RETENTION_DAYS` as evidence of who acted, and removed after.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from oauth2_provider.models import (
    clear_expired,
    get_access_token_model,
    get_grant_model,
    get_refresh_token_model,
)

from phoxtail.tokens.models import AccessToken

# How long a dead phoxtail token row is kept before the sweep removes it. A
# revoked chat-turn credential says who acted and when, which is worth
# keeping for a while.
RETENTION_DAYS = 90


def sweep(retention_days: int = RETENTION_DAYS) -> dict[str, int]:
    """Delete phoxtail's dead token rows older than the retention, and hand
    the authorization server's own families to its sweep. Returns how many
    rows of each kind went."""
    cutoff = timezone.now() - timedelta(days=retention_days)
    # A row with no expiry is a key that never ages; only a revocation kills
    # it. A row past its expiry is dead whether or not anyone revoked it.
    dead = AccessToken.objects.filter(Q(revoked_at__lt=cutoff) | Q(revoked_at__isnull=True, expires_at__lt=cutoff))
    # ``delete()`` counts what cascaded too — search-index entries, for one —
    # and the answer wanted is how many tokens went.
    _, by_model = dead.delete()
    removed = by_model.get(AccessToken._meta.label, 0)
    server_models = (get_access_token_model(), get_refresh_token_model(), get_grant_model())
    before = sum(model.objects.count() for model in server_models)
    clear_expired()
    after = sum(model.objects.count() for model in server_models)
    # Rows minted between the two counts would read as negative removals;
    # the number is for an operator asking whether anything happened.
    return {"phoxtail": removed, "server": max(before - after, 0)}
