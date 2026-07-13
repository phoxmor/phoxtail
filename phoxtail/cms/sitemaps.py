from wagtail.contrib.sitemaps import Sitemap as WagtailSitemap
from wagtail.models import Page


class PageSitemap(WagtailSitemap):
    """All live public pages of the current site, across all locale trees.

    Every page type inheriting wagtail.models.Page — from phoxtail.cms,
    from phoxtail apps, or from the project — shares the page tree and is
    included automatically. A page type opts out by overriding
    ``get_sitemap_urls`` to return ``[]``.
    """

    def items(self):
        root = self.get_wagtail_site().root_page
        roots = Page.objects.live().filter(translation_key=root.translation_key)

        pages = Page.objects.none()
        for locale_root in roots:
            pages |= locale_root.get_descendants(inclusive=True)

        return pages.live().public().order_by("path").specific(defer=True)

    def lastmod(self, obj):
        return obj.last_published_at
