from django.apps import AppConfig


class PhoxtailCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.core"
    label = "phoxtail_core"
    verbose_name = "Phoxtail Core"

    def ready(self) -> None:
        # Mount routers contributed by other PhoxtailAppConfigs onto the
        # shared NinjaAPI instance. Running this from ready() guarantees
        # Django's app registry is fully populated before we iterate it,
        # and avoids the fragility of doing the walk at module-import
        # time (which broke test imports that touch phoxtail.api before
        # django.setup() completes).
        from phoxtail.api import mount_contributed_routers

        mount_contributed_routers()
