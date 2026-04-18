from django.db import models
from django.utils.translation import gettext_lazy as _


class AccessTokensAdminPermission(models.Model):
    """ContentType anchor for tokens admin permissions.

    Never instantiated — its sole purpose is to give Django a content type
    under which the ``Permission`` rows below can be created during
    ``migrate``. Mirrors the pattern used by ``BookingAdminPermission``.
    """

    class Meta:
        default_permissions = ()
        permissions = [
            # ── Access gate ─────────────────────────────────────
            # Required to see the "Access Tokens" menu item at all.
            ("access_tokens_management", "Can access Access Tokens management"),
            # ── Self-service actions ────────────────────────────
            # Holders of these can mint and revoke tokens, but only ever
            # within the scope of their own user account.
            ("create_access_tokens", "Can create Access Tokens"),
            ("revoke_access_tokens", "Can revoke Access Tokens"),
            # ── Org-wide elevation ──────────────────────────────
            # Widens the list view to cover every user's tokens and
            # permits revoking tokens that belong to other users. Gate
            # this tightly: it is effectively "impersonate anyone".
            ("manage_all_tokens", "Can view and revoke tokens across all users"),
        ]

        verbose_name = _("Access Tokens")
        verbose_name_plural = _("Access Tokens")
