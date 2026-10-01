from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailUsersConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.users"
    label = "phoxtail_users"
    verbose_name = "Phoxtail Users"

    # A user's avatar is drawn through sorl's thumbnail tag, so every project
    # that installs this app gets sorl's app with it.
    depends_on = ["sorl.thumbnail"]
