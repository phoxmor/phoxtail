import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Environment Variables
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Core Django Settings
SECRET_KEY = env("SECRET_KEY")
ROOT_URLCONF = "src.urls"
AUTH_USER_MODEL = "phoxtail_users.User"
WSGI_APPLICATION = "src.wsgi.application"

# Installed Applications
INSTALLED_APPS = [
    "phoxtail.core",
    "phoxtail.users",
    "phoxtail.design",
    "phoxtail.streams",
    "phoxtail.cms",
    "phoxtail.tokens",
    # {{ phoxtail_optional_apps }}
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail.contrib.settings",
    "wagtail.locales",
    "wagtail.contrib.simple_translation",
    "wagtail",
    "wagtailmedia",
    "modelcluster",
    "taggit",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    "django_htmx",
    "wagtail.users",
    "{{ phoxtail_project_name }}",
    "allauth",
    "allauth.account",
    "sorl.thumbnail",
    "wagtail_color_panel",
]

# Hosts and Security
ALLOWED_HOSTS = env("ALLOWED_HOSTS", default="").strip(",").split(",")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", default="").strip(",").split(",")
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240

# Middleware
MIDDLEWARE = [
    # Must run before CommonMiddleware so /api/foo is rewritten to /api/foo/
    # in-place (no redirect) — see phoxtail.api.middleware for rationale.
    "phoxtail.api.middleware.ApiTrailingSlashMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# Authentication (django-allauth)
ACCOUNT_ADAPTER = "phoxtail.users.adapters.AccountAdapter"
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_FORMS = {
    "login": "phoxtail.users.forms.LoginForm",
    "signup": "phoxtail.users.forms.SignupForm",
}
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "login_redirect"
LOGOUT_REDIRECT_URL = "/"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
            ],
        },
    },
]

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    }
}

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation"
        ".UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"

USE_I18N = True
WAGTAIL_I18N_ENABLED = True

WAGTAIL_CONTENT_LANGUAGES = LANGUAGES = [
    ("en", "English"),
]

# Static and Media Files
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATIC_URL = "/static/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = "/media/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    },
}

# Wagtail Settings
WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}
WAGTAILIMAGES_EXTENSIONS = [
    "avif",
    "gif",
    "jpg",
    "jpeg",
    "png",
    "webp",
    "svg",
    "ico",
]
WAGTAILDOCS_EXTENSIONS = [
    "csv",
    "docx",
    "key",
    "odt",
    "pdf",
    "pptx",
    "rtf",
    "txt",
    "xlsx",
    "zip",
]

WAGTAILMEDIA = {
    "MEDIA_MODEL": "wagtailmedia.Media",
    "MEDIA_FORM_BASE": "",
    "AUDIO_EXTENSIONS": [
        "aac",
        "aiff",
        "flac",
        "m4a",
        "m4b",
        "mp3",
        "ogg",
        "wav",
    ],
    "VIDEO_EXTENSIONS": [
        "avi",
        "h264",
        "m4v",
        "mkv",
        "mov",
        "mp4",
        "mpeg",
        "mpg",
        "ogv",
        "webm",
    ],
}
WAGTAIL_PASSWORD_REQUIRED_TEMPLATE = "wagtailadmin/pages/password_required.html"
WAGTAIL_FRONTEND_LOGIN_TEMPLATE = "wagtailadmin/pages/login.html"
_protocol = "https" if env("DJANGO_ENV") == "production" else "http"
_domain = env("DOMAIN", default="localhost")
WAGTAILADMIN_BASE_URL = f"{_protocol}://{_domain}"
WAGTAIL_SITE_NAME = env("SITE_NAME", default="{{ phoxtail_project_name }}")

# Email Settings
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Features
PHOXTAIL_ALLOW_SIGNUP = env.bool("PHOXTAIL_ALLOW_SIGNUP", default=False)

# NOTE: PhoxtailAppConfig wiring (wire_apps) is intentionally NOT called
# here. It runs in the concrete settings modules (development.py,
# production.py, test.py) AFTER they finish modifying INSTALLED_APPS, so
# declarations from test-only or env-specific apps are never missed.
