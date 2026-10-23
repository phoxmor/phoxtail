from phoxtail.core.app_config import PhoxtailAppConfig

from .countries import countries_override


class PhoxtailUsersConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.users"
    label = "phoxtail_users"
    verbose_name = "Phoxtail Users"

    # A user's avatar is drawn through sorl's thumbnail tag, so every project
    # that installs this app gets sorl's app with it.
    depends_on = ["sorl.thumbnail"]
    default_settings = {
        # Every country field names countries as the phone prefixes do.
        "COUNTRIES_OVERRIDE": countries_override(),
        # allauth finds a user by email or username, and lets an inactive one
        # through to its "Account Inactive" page; Django's own backend finds
        # one only by email (USERNAME_FIELD) and refuses an inactive one as a
        # wrong password.
        "AUTHENTICATION_BACKENDS": [
            "django.contrib.auth.backends.ModelBackend",
            "allauth.account.auth_backends.AuthenticationBackend",
        ],
    }
