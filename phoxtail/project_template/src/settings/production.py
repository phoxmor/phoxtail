from .base import *  # noqa: F403

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

USE_SMTP_EMAIL_BACKEND = env.bool("USE_SMTP_EMAIL_BACKEND", default=False)  # noqa: F405
if USE_SMTP_EMAIL_BACKEND:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")  # noqa: F405
    EMAIL_PORT = env.int("EMAIL_PORT")  # noqa: F405
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")  # noqa: F405
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")  # noqa: F405
    DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")  # noqa: F405
