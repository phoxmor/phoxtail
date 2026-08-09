"""Minimal Django settings for running phoxtail.core tests."""

import tempfile

SECRET_KEY = "test-secret-key-not-for-production"

# Without MEDIA_ROOT, FileField uploads resolve against the process cwd and
# leak into whatever repo the tests run from.
MEDIA_ROOT = tempfile.mkdtemp(prefix="phoxtail-test-media-")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

AUTH_USER_MODEL = "phoxtail_users.User"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django_htmx",
    "allauth",
    "allauth.account",
    "taggit",
    "modelcluster",
    "wagtail",
    "wagtail.admin",
    "wagtail.embeds",
    "wagtail.images",
    "wagtail.documents",
    "wagtail.search",
    "wagtail.snippets",
    "wagtail.sites",
    "wagtail.locales",
    "wagtail.users",
    "wagtailmedia",
    "phoxtail.core",
    "phoxtail.users",
    "phoxtail.media",
    "phoxtail.core.tests.testapp",
    "phoxtail.design",
    "phoxtail.streams",
    "phoxtail.remotes",
    "phoxtail.cms",
    "phoxtail.agent",
    "phoxtail.dashboard",
    "phoxtail.tokens",
    # After the phoxtail apps, as in the hatched project template: phoxtail.cms
    # installs its draft-redirect guard before this app connects the handler,
    # which is the order the guard is written for. See phoxtail/cms/signals.py.
    "wagtail.contrib.redirects",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# Authentication (django-allauth) — mirrors the project template so the
# users service layer (adapter + EmailAddress orchestration) is exercised
# with production wiring.
ACCOUNT_ADAPTER = "phoxtail.users.adapters.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
PHOXTAIL_ALLOW_SIGNUP = False

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

WAGTAILIMAGES_IMAGE_MODEL = "phoxtail_media.PhoxtailImage"
WAGTAILDOCS_DOCUMENT_MODEL = "phoxtail_media.PhoxtailDocument"
WAGTAILMEDIA = {"MEDIA_MODEL": "phoxtail_media.PhoxtailMedia"}
