from .base import *

DEBUG = True

INSTALLED_APPS += ["django_browser_reload", "django_extensions"]
MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]

INTERNAL_IPS = ["127.0.0.1"]
