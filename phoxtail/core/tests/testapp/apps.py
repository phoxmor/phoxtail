from django.apps import AppConfig


class TestAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.core.tests.testapp"
    label = "phoxtail_core_testapp"
