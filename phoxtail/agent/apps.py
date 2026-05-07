from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount


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

    api_version_router = "phoxtail.agent.api.v1.router"
    url_mount = UrlMount(
        prefix="phoxtail-agent/",
        module="phoxtail.agent.urls",
        namespace="phoxtail_agent",
    )
