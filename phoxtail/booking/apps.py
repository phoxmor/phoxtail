from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailBookingConfig(PhoxtailAppConfig):
    name = "phoxtail.booking"
    label = "phoxtail_booking"
    verbose_name = "Phoxtail Booking"

    depends_on = [
        "phoxtail.dashboard",
        "phoxtail.booking.core",
        "phoxtail.booking.services",
        "phoxtail.booking.events",
        "phoxtail.booking.subscriptions",
        "phoxtail.booking.reservations",
        "django_celery_beat",
    ]
    requires_celery = True
    default_settings = {
        "CELERY_BROKER_URL": "redis://redis:6379/0",
        "CELERY_RESULT_BACKEND": "redis://redis:6379/0",
        "CELERY_ACCEPT_CONTENT": ["json"],
        "CELERY_TASK_SERIALIZER": "json",
        "CELERY_RESULT_SERIALIZER": "json",
        "CELERY_TASK_TRACK_STARTED": True,
        "CELERY_TASK_TIME_LIMIT": 30 * 60,
    }
    requirements = ["celery", "django-celery-beat"]
