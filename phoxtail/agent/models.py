from django.conf import settings
from django.db import models
from wagtail.search import index

from phoxtail.core.mixins import TimestampMixin, UUIDMixin


class Conversation(UUIDMixin, TimestampMixin, index.Indexed):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    message_history = models.JSONField(default=list)
    title = models.CharField(max_length=255, blank=True, default="")

    search_fields = [
        index.SearchField("title"),
        index.AutocompleteField("title"),
        index.FilterField("user"),
    ]

    class Meta:
        ordering = ["-updated_at", "-id"]
