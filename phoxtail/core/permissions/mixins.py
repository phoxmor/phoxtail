from typing import ClassVar

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils.translation import gettext as _
from django_htmx.http import trigger_client_event

from .policies import AppPermissionPolicy


class PermissionMixin:
    """
    Generic CBV mixin for permission-protected admin views.

    Subclasses set:
      - `permission_policy` — an AppPermissionPolicy instance
      - `required_permissions` — list of codenames (ALL required)

    Must be placed BEFORE the view class in MRO so dispatch() runs first.

    Usage:
        class MySearchView(BookingPermissionMixin, SingleSelectSearchView):
            required_permissions = ["access_booking_management", "manage_reservations"]
    """

    permission_policy: ClassVar[AppPermissionPolicy | None] = None
    required_permissions: ClassVar[list[str]] = []

    def dispatch(self, request, *args, **kwargs):
        if self.permission_policy:
            for perm in self.required_permissions:
                if not self.permission_policy.user_has_permission(request.user, perm):
                    # HTMX requests: return 204 with a client event
                    # that triggers an error toast and closes any open
                    # modal. Raising PermissionDenied would let Wagtail's
                    # middleware convert it to a 302 redirect, which HTMX
                    # follows transparently — breaking the page layout.
                    if getattr(request, "htmx", None):
                        response = HttpResponse(status=204)
                        trigger_client_event(
                            response,
                            "showToast",
                            {
                                "message": _("You do not have permission to perform this action."),
                                "type": "error",
                            },
                        )
                        return response
                    raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
