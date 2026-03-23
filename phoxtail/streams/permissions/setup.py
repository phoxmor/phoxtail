from phoxtail.core.permissions import (
    AppPermissionPolicy,
    PermissionedViewSet,
    PermissionMixin,
    permission_required_factory,
)

from .models import StreamsAdminPermission

streams_permission_policy = AppPermissionPolicy(StreamsAdminPermission)

streams_permission_required = permission_required_factory(streams_permission_policy)


class StreamsPermissionMixin(PermissionMixin):
    """Streams-specific CBV mixin. Subclasses only need to set required_permissions."""

    permission_policy = streams_permission_policy


class StreamsViewSet(PermissionedViewSet):
    """
    Base ViewSet for streams admin views. Subclasses set required_permissions.
    """

    permission_policy = streams_permission_policy
