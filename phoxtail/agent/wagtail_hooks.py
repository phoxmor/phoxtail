from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from phoxtail.agent.models import InferenceProvider, ModelArtifact
from phoxtail.agent.permissions.models import AgentAdminPermission


@hooks.register("register_permissions")
def register_agent_permissions():
    content_type = ContentType.objects.get_for_model(AgentAdminPermission)
    return Permission.objects.filter(content_type=content_type)


class InferenceProviderViewSet(SnippetViewSet):
    model = InferenceProvider
    list_display = [
        "display_name",
        "model_prefix",
        "base_url",
        "api_key_env_var",
        "is_active",
    ]
    # api_key_env_var is shown deliberately — env var names are not secrets,
    # and operators need to see at a glance whether a provider is misconfigured.


class ModelArtifactViewSet(SnippetViewSet):
    model = ModelArtifact
    list_display = [
        "display_name",
        "provider",
        "identifier",
        "permission",
        "is_active",
        "sort_order",
    ]


register_snippet(InferenceProviderViewSet)
register_snippet(ModelArtifactViewSet)
