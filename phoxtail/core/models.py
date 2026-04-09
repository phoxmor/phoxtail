import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin

logger = logging.getLogger(__name__)


@register_snippet
class InternalLink(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed):
    """A named Django route exposed as a Wagtail snippet for use in StreamField blocks."""

    label = models.CharField(
        max_length=255,
        help_text=_("Display text for this link (e.g. 'My Subscriptions')"),
    )
    url_name = models.CharField(
        max_length=255,
        unique=True,
        help_text=_("Django URL name (e.g. 'dashboard:index')"),
    )

    panels = [
        FieldPanel("label"),
        FieldPanel("url_name"),
    ]

    search_fields = [
        index.AutocompleteField("label"),
        index.SearchField("url_name"),
    ]

    def clean(self):
        super().clean()
        try:
            reverse(self.url_name)
        except NoReverseMatch:
            raise ValidationError(
                {
                    "url_name": _(
                        "Not a valid URL name. Run 'phoxtail manage show_urls' to see available choices."
                    )
                },
            )

    @property
    def url(self):
        try:
            return reverse(self.url_name)
        except NoReverseMatch:
            logger.warning(
                "InternalLink '%s' has invalid url_name '%s'", self.label, self.url_name
            )
            return "#"

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = _("Internal Link")
        verbose_name_plural = _("Internal Links")
        ordering = ["label"]
