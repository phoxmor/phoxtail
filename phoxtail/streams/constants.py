from django.db import models
from django.utils.translation import gettext_lazy as _


class WORKFLOW_CHOICES(models.TextChoices):
    """Workflow choices for Studio context form."""

    CREATE = "create", _("Create Variant")
    EDIT = "edit", _("Edit Variant")
