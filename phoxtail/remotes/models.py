from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from wagtail.search import index

from phoxtail.core.mixins import TimestampMixin, UUIDMixin


class Remote(UUIDMixin, TimestampMixin, index.Indexed, models.Model):
    """A connection to another Phoxtail project — peer, registry, or swarm node."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Display label for this remote (e.g. 'Phoxtail Registry')."),
    )
    base_url = models.URLField(
        unique=True,
        help_text=_("Root URL of the remote project, e.g. https://registry.phoxtail.com — no trailing slash."),
    )
    token = models.CharField(
        max_length=200,
        help_text=_("Bearer token for this remote. Never displayed after save."),
    )

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("name"),
        index.AutocompleteField("base_url"),
        index.SearchField("base_url"),
    ]

    class Meta:
        verbose_name = _("Remote")
        verbose_name_plural = _("Remotes")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.base_url:
            self.base_url = self.base_url.rstrip("/")

    def get_admin_url(self):
        return reverse("remotes:index")

    @property
    def token_fingerprint(self):
        t = self.token
        if not t:
            return "—"
        if len(t) <= 8:
            return t[:2] + "…"
        return t[:6] + "…" + t[-4:]
