from .base import *  # noqa: F403

DEBUG = True

INSTALLED_APPS += ["django_browser_reload", "django_extensions"]  # noqa: F405
MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]
