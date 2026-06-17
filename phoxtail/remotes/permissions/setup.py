from phoxtail.core.permissions import (
    AppPermissionPolicy,
    PermissionedViewSet,
    PermissionMixin,
    permission_required_factory,
)

from .models import RemotesAdminPermission

remotes_permission_policy = AppPermissionPolicy(RemotesAdminPermission)

remotes_permission_required = permission_required_factory(remotes_permission_policy)


class RemotesPermissionMixin(PermissionMixin):
    permission_policy = remotes_permission_policy


class RemotesPermissionedViewSet(PermissionedViewSet):
    permission_policy = remotes_permission_policy
