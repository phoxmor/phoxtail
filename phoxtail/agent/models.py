from django.conf import settings
from django.db import models

from phoxtail.core.mixins import TimestampMixin, UUIDMixin


class Conversation(UUIDMixin, TimestampMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    message_history = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at", "-id"]
