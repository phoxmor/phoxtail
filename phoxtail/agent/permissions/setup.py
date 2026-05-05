from phoxtail.core.permissions import (
    AppPermissionPolicy,
    PermissionedViewSet,
    PermissionMixin,
    permission_required_factory,
)

from .models import AgentAdminPermission

agent_permission_policy = AppPermissionPolicy(AgentAdminPermission)
agent_permission_required = permission_required_factory(agent_permission_policy)


class AgentPermissionMixin(PermissionMixin):
    permission_policy = agent_permission_policy


class AgentViewSet(PermissionedViewSet):
    permission_policy = agent_permission_policy
