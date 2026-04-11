from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount


class PhoxtailDashboardConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.dashboard"
    label = "phoxtail_dashboard"
    verbose_name = "Phoxtail Dashboard"

    url_mount = UrlMount(prefix="dashboard/", module="phoxtail.dashboard.urls")
    context_processors = [
        "phoxtail.dashboard.context_processors.dashboard_nav",
    ]

    def ready(self):
        from django.utils.module_loading import autodiscover_modules

        autodiscover_modules("dashboard")
