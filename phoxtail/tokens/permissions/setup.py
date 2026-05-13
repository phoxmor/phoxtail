from phoxtail.core.permissions import (
    AppPermissionPolicy,
    PermissionedViewSet,
    PermissionMixin,
    permission_required_factory,
)

from .models import AccessTokensAdminPermission

# ── Policy singleton ────────────────────────────────────────────
access_tokens_permission_policy = AppPermissionPolicy(AccessTokensAdminPermission)

# ── FBV decorator ───────────────────────────────────────────────
access_tokens_permission_required = permission_required_factory(access_tokens_permission_policy)


# ── CBV mixin (pre-wired with access-tokens policy) ────────────
class AccessTokensPermissionMixin(PermissionMixin):
    """CBV mixin for access-token admin views. Subclasses set ``required_permissions``."""

    permission_policy = access_tokens_permission_policy


# ── Base ViewSet (pre-wired with access-tokens policy) ─────────
class AccessTokensViewSet(PermissionedViewSet):
    """Base ViewSet for access-token admin views. Subclasses set ``required_permissions``."""

    permission_policy = access_tokens_permission_policy
