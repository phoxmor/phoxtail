from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailTokensConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.tokens"
    label = "phoxtail_tokens"
    verbose_name = "Phoxtail Tokens"
