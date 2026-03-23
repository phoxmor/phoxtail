from django.apps import AppConfig


class PhoxtailStreamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.streams"
    label = "phoxtail_streams"
    verbose_name = "Phoxtail Streams"

    def ready(self):
        from phoxtail.streams.signals import connect_cache_signals

        connect_cache_signals()
