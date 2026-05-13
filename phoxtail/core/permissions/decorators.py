from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils.translation import gettext as _
from django_htmx.http import trigger_client_event


def permission_required_factory(policy):
    """
    Creates an app-specific permission decorator bound to a policy.

    Usage:
        # In your app's permissions/setup.py
        my_permission_required = permission_required_factory(my_policy)

        # Then in views:
        @booking_permission_required("access_booking_management", "manage_reservations")
        def my_view(request):
            ...
    """

    def permission_required(*permission_codenames):
        def decorator(view_func):
            @wraps(view_func)
            def _wrapped(request, *args, **kwargs):
                for perm in permission_codenames:
                    if not policy.user_has_permission(request.user, perm):
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
                return view_func(request, *args, **kwargs)

            return _wrapped

        return decorator

    return permission_required
