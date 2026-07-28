from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.viewsets.model import ModelViewSetGroup

from phoxtail.agent.permissions.models import AgentAdminPermission
from phoxtail.agent.viewsets import InferenceProviderViewSet, ModelArtifactViewSet


@hooks.register("register_permissions")
def register_agent_permissions():
    content_type = ContentType.objects.get_for_model(AgentAdminPermission)
    return Permission.objects.filter(content_type=content_type)


@hooks.register("register_admin_viewset")
class AgentViewSetGroup(ModelViewSetGroup):
    menu_label = _("Inference")
    menu_icon = "cognition"
    show_in_menu = True
    menu_order = 300
    items = (
        InferenceProviderViewSet,
        ModelArtifactViewSet,
    )
