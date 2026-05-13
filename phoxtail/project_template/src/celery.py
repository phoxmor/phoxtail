import os
from pathlib import Path

import environ
from celery import Celery

BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

env = os.environ.get("DJANGO_ENV", "development")
settings_module = f"src.settings.{env}"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)

CELERY_APP_NAME = os.getenv("CELERY_APP_NAME", "{{ phoxtail_project_name }}") or "{{ phoxtail_project_name }}"

app = Celery(CELERY_APP_NAME)
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
