from functools import cached_property
from typing import ClassVar

from wagtail.admin.menu import MenuItem
from wagtail.admin.viewsets.base import ViewSet

from .policies import AppPermissionPolicy


class PermissionedViewSet(ViewSet):
    """
    Base ViewSet for custom admin views with permission support.

    Subclasses MUST set:
      - `permission_policy` — an AppPermissionPolicy instance
      - `required_permissions` — list of permission codenames

    These control:
      1. Menu item visibility (is_shown)
      2. The minimum permissions to access any view in this viewset

    Individual views should add stricter checks via the app-specific
    permission decorator for fine-grained action control.
    """

    permission_policy: ClassVar[AppPermissionPolicy | None] = None
    required_permissions: ClassVar[list[str]] = []

    @cached_property
    def menu_item_class(self):
        policy = self.permission_policy
        perms = self.required_permissions

        def is_shown(_self, request):
            if not policy or not perms:
                return True
            return policy.user_has_any_permission(request.user, perms)

        return type(
            f"{self.__class__.__name__}MenuItem",
            (MenuItem,),
            {"is_shown": is_shown},
        )
