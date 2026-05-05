from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from wagtail import hooks

from phoxtail.agent.permissions.models import AgentAdminPermission


@hooks.register("register_permissions")
def register_agent_permissions():
    content_type = ContentType.objects.get_for_model(AgentAdminPermission)
    return Permission.objects.filter(content_type=content_type)
