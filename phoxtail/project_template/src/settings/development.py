from .base import *  # noqa: F403

DEBUG = True

INSTALLED_APPS += ["django_browser_reload", "django_extensions"]  # noqa: F405
MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Autonomous app wiring — must run AFTER INSTALLED_APPS / TEMPLATES /
# MIDDLEWARE and any user-authored settings that apps should not
# override. Merges PhoxtailAppConfig declarations into this module.
from phoxtail.core.wiring import wire_apps  # noqa: E402

wire_apps(globals())
