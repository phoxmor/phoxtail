from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailAgentConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.agent"
    label = "phoxtail_agent"
    verbose_name = "Phoxtail Agent"

    depends_on = [
        "phoxtail.core",
    ]

    api_version_router = "phoxtail.agent.api.v1.router"
