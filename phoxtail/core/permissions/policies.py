from wagtail.permission_policies.base import BasePermissionPolicy


class AppPermissionPolicy(BasePermissionPolicy):
    """
    Generic permission policy for custom admin views.

    Works with any Django model that serves as a ContentType anchor
    for permissions (the "permission model" pattern). Each app cluster
    creates a singleton instance pointed at its own permission model.

    Usage:
        from phoxtail.core.permissions import AppPermissionPolicy
        from .models import BookingAdminPermission

        booking_permission_policy = AppPermissionPolicy(BookingAdminPermission)
    """

    def __init__(self, permission_model):
        super().__init__(permission_model)
        self._app_label = permission_model._meta.app_label

    def _full_perm(self, action):
        return f"{self._app_label}.{action}"

    def user_has_permission(self, user, action):
        if not user.is_active:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(self._full_perm(action))

    def user_has_any_permission(self, user, actions):
        if not user.is_active:
            return False
        if user.is_superuser:
            return True
        return any(user.has_perm(self._full_perm(a)) for a in actions)
