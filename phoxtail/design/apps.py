from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailDesignConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.design"
    label = "phoxtail_design"
    verbose_name = "Phoxtail Design"
