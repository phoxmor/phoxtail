from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailUsersConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.users"
    label = "phoxtail_users"
    verbose_name = "Phoxtail Users"
