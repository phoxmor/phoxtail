"""Minimal Django settings for running phoxtail.core tests."""

SECRET_KEY = "test-secret-key-not-for-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django_htmx",
    "taggit",
    "modelcluster",
    "wagtail",
    "wagtail.admin",
    "wagtail.images",
    "wagtail.search",
    "wagtail.sites",
    "wagtail.locales",
    "wagtail.users",
    "phoxtail.core",
    "phoxtail.core.tests.testapp",
    "phoxtail.design",
    "phoxtail.streams",
    "phoxtail.dashboard",
    "django_countries",
    "phonenumber_field",
    "timezone_field",
    "django_celery_beat",
    "django_filters",
    "wagtailmedia",
    "phoxtail.booking.core",
    "phoxtail.booking.events",
    "phoxtail.booking.services",
    "phoxtail.booking.subscriptions",
    "phoxtail.booking.reservations",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

ROOT_URLCONF = "phoxtail.core.urls"

STATIC_URL = "/static/"

WAGTAILADMIN_BASE_URL = "http://localhost:8000"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
