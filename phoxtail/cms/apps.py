from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailCmsConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.cms"
    label = "phoxtail_cms"
    verbose_name = "Phoxtail CMS"

    depends_on = [
        "phoxtail.design",
        "phoxtail.streams",
    ]
