from phoxtail.core.app_config import PhoxtailAppConfig


class ProjectConfig(PhoxtailAppConfig):
    """This project's own app.

    Subclasses PhoxtailAppConfig like every phoxtail app, so the project can
    grow its own surfaces the same way an installed package does: add an
    ``api/`` package declaring ``versions`` and it is served at
    ``/api/<label>/<version>/``; add an ``mcp/`` package and its tools appear.
    Neither is declared anywhere — they are found.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "{{ phoxtail_project_name }}"
