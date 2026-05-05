from django.db import models
from django.utils.translation import gettext_lazy as _


class AgentAdminPermission(models.Model):
    """ContentType anchor for agent permissions — never instantiated."""

    class Meta:
        default_permissions = ()
        permissions = [
            ("access_chatbot", "Can access the AI chatbot"),
        ]
        verbose_name = _("Agent")
        verbose_name_plural = _("Agent")
