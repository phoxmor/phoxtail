from .base import *  # noqa: F403

# Use a fast (unsalted) hasher so tests that create users don't burn time
# on PBKDF2 iterations.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Skip the static-file manifest so tests never require a collectstatic run.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Autonomous app wiring — must run AFTER any test-only INSTALLED_APPS
# modifications above. Merges PhoxtailAppConfig declarations into this
# module.
from phoxtail.core.wiring import wire_apps  # noqa: E402

wire_apps(globals())
