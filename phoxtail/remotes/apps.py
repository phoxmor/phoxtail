from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailRemotesConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.remotes"
    label = "phoxtail_remotes"
    verbose_name = "Phoxtail Remotes"
