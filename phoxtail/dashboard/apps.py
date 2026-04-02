from django.apps import AppConfig


class PhoxtailDashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.dashboard"
    label = "phoxtail_dashboard"
    verbose_name = "Phoxtail Dashboard"

    def ready(self):
        from django.utils.module_loading import autodiscover_modules

        autodiscover_modules("dashboard")
