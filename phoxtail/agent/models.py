from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.models import Orderable
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin


class InferenceProvider(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, models.Model):
    identifier = models.SlugField(unique=True, verbose_name=_("identifier"))
    display_name = models.CharField(max_length=100, verbose_name=_("display name"))
    model_prefix = models.CharField(max_length=64, blank=True, verbose_name=_("model prefix"))
    base_url = models.URLField(blank=True, verbose_name=_("base URL"))
    api_key_env_var = models.CharField(max_length=200, blank=True, verbose_name=_("API key environment variable"))
    is_active = models.BooleanField(default=True, verbose_name=pgettext_lazy("state", "active"))

    search_fields = [
        index.SearchField("display_name"),
        index.AutocompleteField("display_name"),
        index.FilterField("is_active"),
    ]

    class Meta:
        verbose_name = _("inference provider")
        verbose_name_plural = _("inference providers")
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name


class ModelArtifact(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, Orderable):
    provider = models.ForeignKey(
        InferenceProvider, on_delete=models.CASCADE, related_name="artifacts", verbose_name=_("provider")
    )
    identifier = models.CharField(max_length=200, verbose_name=_("identifier"))
    display_name = models.CharField(max_length=100, verbose_name=_("display name"))
    permission = models.ForeignKey(
        "auth.Permission",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=pgettext_lazy("access", "permission"),
    )
    is_active = models.BooleanField(default=True, verbose_name=pgettext_lazy("state", "active"))

    search_fields = [
        index.SearchField("display_name"),
        index.SearchField("identifier"),
        index.AutocompleteField("display_name"),
        index.AutocompleteField("identifier"),
        index.FilterField("is_active"),
        index.FilterField("provider"),
        index.FilterField("sort_order"),
        index.RelatedFields(
            "provider",
            [
                index.FilterField("is_active"),
                index.AutocompleteField("display_name"),
            ],
        ),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("AI model")
        verbose_name_plural = _("AI models")
        unique_together = [["provider", "identifier"]]

    def __str__(self):
        return f"{self.display_name} ({self.provider.display_name})"


class Conversation(UUIDMixin, TimestampMixin, index.Indexed):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_conversations", verbose_name=_("user")
    )
    message_history = models.JSONField(default=list, verbose_name=_("message history"))
    title = models.CharField(max_length=255, blank=True, default="", verbose_name=_("title"))
    last_artifact_used = models.ForeignKey(
        "ModelArtifact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("last artifact used"),
    )

    search_fields = [
        index.SearchField("title"),
        index.AutocompleteField("title"),
        index.FilterField("user"),
    ]

    class Meta:
        verbose_name = _("conversation")
        verbose_name_plural = _("conversations")
        ordering = ["-updated_at", "-id"]


@register_setting(icon="cognition")
class AgentSiteSetting(BaseSiteSetting):
    default_artifact = models.ForeignKey(
        ModelArtifact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("default artifact"),
    )

    panels = [FieldPanel("default_artifact")]

    class Meta:
        verbose_name = _("Inference")
