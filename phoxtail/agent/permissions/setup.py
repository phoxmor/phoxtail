from functools import wraps

from django.core.exceptions import PermissionDenied

from phoxtail.core.permissions import (
    AppPermissionPolicy,
    PermissionedViewSet,
    PermissionMixin,
    permission_required_factory,
)

from .models import AgentAdminPermission

agent_permission_policy = AppPermissionPolicy(AgentAdminPermission)
agent_permission_required = permission_required_factory(agent_permission_policy)


def operator_required(view):
    """Only an active operator may reach this view.

    The blunt instrument, and used here for a reason rather than for
    convenience: the pickers it guards serve querysets that are not
    narrowed to the caller. Every image, document and collection in the
    project is returned, so the honest answer to "who may see this" is
    "someone who may see everything".

    Prefer :func:`agent_permission_required` wherever the act has a name.
    This is what to reach for while a surface shows more than the person
    asking is entitled to — and the better fix, when it comes, is to
    narrow the queryset and then name a permission, at which point this
    decorator comes back off.

    ``is_active`` is part of the question. A deactivated operator is not
    one, and writing ``user.is_superuser`` by hand at each view is how
    that gets forgotten.
    """

    @wraps(view)
    def guarded(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not (user and user.is_active and user.is_superuser):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return guarded


class AgentPermissionMixin(PermissionMixin):
    permission_policy = agent_permission_policy


class AgentViewSet(PermissionedViewSet):
    permission_policy = agent_permission_policy
