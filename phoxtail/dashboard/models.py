"""The menu an editor writes for the platform.

Apps register their own dashboard entries in code (``registry.DashboardNavItem``);
those follow the software. A Menu is the other kind — written in the admin,
scoped to a site and a language like shared block content is, and free to say
whatever a particular deployment needs.

Resolution is exact: a menu asked for in a language it was never written in is
absent, not silently answered in another language.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.fields import StreamField
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin
from phoxtail.dashboard.blocks import MenuStreamBlock


class Menu(UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, models.Model):
    site = models.ForeignKey(
        "wagtailcore.Site",
        on_delete=models.CASCADE,
        related_name="dashboard_menus",
        verbose_name=_("Site"),
    )
    locale = models.ForeignKey(
        "wagtailcore.Locale",
        on_delete=models.CASCADE,
        related_name="dashboard_menus",
        verbose_name=_("Locale"),
    )
    items = StreamField(
        MenuStreamBlock(),
        blank=True,
        verbose_name=_("Items"),
        help_text=_("The entries of this menu, in the order they are shown."),
    )

    search_fields = [
        index.FilterField("site"),
        index.FilterField("locale"),
    ]

    class Meta:
        # "Platform", not "Dashboard": the contrast being drawn is with the
        # website, and it is the word the rest of this app's prose already
        # uses. Wagtail titles its own admin home "Dashboard", so the name
        # would also read as though this governed that page.
        verbose_name = _("Platform Menu")
        verbose_name_plural = _("Platform Menus")
        constraints = [
            models.UniqueConstraint(
                fields=["site", "locale"],
                name="unique_dashboard_menu",
            )
        ]

    def __str__(self):
        return f"{self.site} / {self.locale}"
