from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.models import Orderable
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin


class InferenceProvider(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, models.Model
):
    identifier = models.SlugField(unique=True)
    display_name = models.CharField(max_length=100)
    model_prefix = models.CharField(max_length=64, blank=True)
    base_url = models.URLField(blank=True)
    api_key_env_var = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    search_fields = [
        index.SearchField("display_name"),
        index.AutocompleteField("display_name"),
        index.FilterField("is_active"),
    ]

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name


class ModelArtifact(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, Orderable):
    provider = models.ForeignKey(
        InferenceProvider, on_delete=models.CASCADE, related_name="artifacts"
    )
    identifier = models.CharField(max_length=200)
    display_name = models.CharField(max_length=100)
    permission = models.ForeignKey(
        "auth.Permission",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_active = models.BooleanField(default=True)

    search_fields = [
        index.SearchField("display_name"),
        index.SearchField("identifier"),
        index.FilterField("is_active"),
        index.FilterField("provider"),
    ]

    class Meta(Orderable.Meta):
        unique_together = [["provider", "identifier"]]

    def __str__(self):
        return f"{self.display_name} ({self.provider.display_name})"


class Conversation(UUIDMixin, TimestampMixin, index.Indexed):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    message_history = models.JSONField(default=list)
    title = models.CharField(max_length=255, blank=True, default="")
    last_artifact_used = models.ForeignKey(
        "ModelArtifact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    search_fields = [
        index.SearchField("title"),
        index.AutocompleteField("title"),
        index.FilterField("user"),
    ]

    class Meta:
        ordering = ["-updated_at", "-id"]


@register_setting(icon="cognition-2")
class AgentSiteSetting(BaseSiteSetting):
    default_artifact = models.ForeignKey(
        ModelArtifact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    panels = [FieldPanel("default_artifact")]

    class Meta:
        verbose_name = _("Agent")
