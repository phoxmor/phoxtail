from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount

from .constants import DEFAULT_INDEX_VIEW


class PhoxtailDashboardConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.dashboard"
    label = "phoxtail_dashboard"
    verbose_name = "Phoxtail Dashboard"

    # Menus point at InternalLink snippets, so core is not optional here.
    depends_on = ["phoxtail.core"]

    url_mount = UrlMount(prefix="dashboard/", module="phoxtail.dashboard.urls")
    context_processors = [
        "phoxtail.dashboard.context_processors.dashboard_nav",
    ]
    default_settings = {
        "PHOXTAIL_DASHBOARD_VIEW": DEFAULT_INDEX_VIEW,
    }

    def ready(self):
        from django.utils.module_loading import autodiscover_modules

        autodiscover_modules("dashboard")
