from importlib.util import find_spec

from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount

# Availability probe from package metadata only — actually importing
# pydantic_ai here would load it into every process at django.setup()
# (~50MB RSS each), paid even by deployments that never use the chatbot.
_HAS_CHATBOT = find_spec("pydantic_ai") is not None


class PhoxtailAgentConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.agent"
    label = "phoxtail_agent"
    verbose_name = "Phoxtail Agent"

    depends_on = [
        "phoxtail.core",
        "phoxtail.media",
        "phoxtail.cms",
    ]

    api_version_router = "phoxtail.agent.api.v1.router" if _HAS_CHATBOT else None
    url_mount = UrlMount(
        prefix="phoxtail-agent/",
        module="phoxtail.agent.urls",
        namespace="phoxtail_agent",
    )
