from phoxtail.core.permissions import (
    AppPermissionPolicy,
    PermissionedViewSet,
    PermissionMixin,
    permission_required_factory,
)

from .models import BookingAdminPermission

# ── Policy singleton ────────────────────────────────────────────
booking_permission_policy = AppPermissionPolicy(BookingAdminPermission)

# ── FBV decorator ───────────────────────────────────────────────
booking_permission_required = permission_required_factory(booking_permission_policy)


# ── CBV mixin (pre-wired with booking policy) ──────────────────
class BookingPermissionMixin(PermissionMixin):
    """Booking-specific CBV mixin. Subclasses only need to set required_permissions."""

    permission_policy = booking_permission_policy


# ── Base ViewSet (pre-wired with booking policy) ────────────────
class BookingViewSet(PermissionedViewSet):
    """
    Base ViewSet for booking admin views. Subclasses set required_permissions.

    Usage:
        class BookingManagementViewSet(BookingViewSet):
            required_permissions = ["access_booking_management"]
    """

    permission_policy = booking_permission_policy
