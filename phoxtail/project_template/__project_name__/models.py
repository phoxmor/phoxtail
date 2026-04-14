from django.utils.translation import gettext_lazy as _

from phoxtail.cms.models import SitePage


class HomePage(SitePage):
    """Starting point for your site — edit freely or subclass SitePage for
    additional page types.
    """

    class Meta:
        verbose_name = _("Home Page")
        verbose_name_plural = _("Home Pages")
