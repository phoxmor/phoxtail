from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailMediaConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.media"
    label = "phoxtail_media"
    verbose_name = "Phoxtail Media"
