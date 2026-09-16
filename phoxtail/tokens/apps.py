from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount
from phoxtail.tokens import provider


class PhoxtailTokensConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.tokens"
    label = "phoxtail_tokens"
    verbose_name = "Phoxtail Tokens"

    # A DOT token is a credential like the ones this app already owns, so
    # the authorization server is this app's surface: pulled into
    # INSTALLED_APPS through the dependency, mounted through the URL mount,
    # configured through the defaults — every hatched project picks all
    # three up on upgrade with nothing edited by hand.
    depends_on = ["oauth2_provider"]
    # At the root, not under a prefix: the discovery document has to sit at
    # /.well-known/ on the origin, because that is the only address a client
    # can compute from the site's name alone. Everything else is under o/.
    url_mount = UrlMount(prefix="", module="phoxtail.tokens.urls")
    default_settings = {"OAUTH2_PROVIDER": provider.defaults()}

    def ready(self):
        # A project that defines OAUTH2_PROVIDER itself replaces these
        # defaults wholesale; the checks say so at startup.
        from phoxtail.tokens import checks  # noqa: F401
