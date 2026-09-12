from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailStreamsConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.streams"
    label = "phoxtail_streams"
    verbose_name = "Phoxtail Streams"

    def ready(self):
        from phoxtail.streams.signals import connect_cache_signals

        connect_cache_signals()
