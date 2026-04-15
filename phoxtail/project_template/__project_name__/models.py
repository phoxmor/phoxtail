from django.utils.translation import gettext_lazy as _

from phoxtail.cms.models import SitePage


class ContentPage(SitePage):
    """General-purpose page type — edit freely or add new models subclassing
    SitePage for additional page types.
    """

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
