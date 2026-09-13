"""Django settings for testing phoxtail and anything built on it.

Shipped deliberately. A package that adds an app to phoxtail needs a Django
configured the way phoxtail configures one, and the alternative is every such
package keeping its own copy of this file and watching the copies drift.

Use it as the base and append:

    from phoxtail.core.test_settings import *  # noqa: F401, F403

    INSTALLED_APPS = [*INSTALLED_APPS, "my_app"]  # noqa: F405

Two orderings below are load-bearing rather than tidy, and are commented where
they occur. Keep them if you rebuild this list rather than append to it.

Not a template for production settings: sqlite in memory, a fixed SECRET_KEY,
and no security middleware. The project template is where production wiring
lives.
"""

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
    # Before wagtail.snippets: that app's ready() searches every app for
    # wagtail_hooks, and wagtailmedia's hooks module looks up the media
    # permission policy. Looking it up creates a fallback policy, after
    # which wagtailmedia's own ready() can no longer register the real one.
    "wagtailmedia",
    "wagtail.snippets",
    "wagtail.sites",
    "wagtail.locales",
    "wagtail.users",
    "phoxtail.core",
    "phoxtail.users",
    "phoxtail.media",
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
