"""Minimal Django settings for running phoxtail.streams tests."""

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
    "wagtail.documents",
    "wagtail.search",
    "wagtail.sites",
    "wagtail.locales",
    "wagtail.users",
    "wagtailmedia",
    "phoxtail.core",
    "phoxtail.media",
    "phoxtail.design",
    "phoxtail.streams",
]

WAGTAILIMAGES_IMAGE_MODEL = "phoxtail_media.PhoxtailImage"
WAGTAILDOCS_DOCUMENT_MODEL = "phoxtail_media.PhoxtailDocument"
WAGTAILMEDIA = {"MEDIA_MODEL": "phoxtail_media.PhoxtailMedia"}

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
