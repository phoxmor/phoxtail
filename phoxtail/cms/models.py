from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.admin.panels.group import ObjectList, TabbedInterface
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.models import Orderable, Page

from .streams import BodyStreamField


class SitePage(Page):
    body = BodyStreamField
    is_locked_for_references = models.BooleanField(
        default=False,
        verbose_name=_("Lock References"),
        help_text=_(
            "If checked, links to this page will appear disabled on the website"
            " and won't redirect."
        ),
    )

    template = "phoxtail_cms/pages/page.html"

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    promote_panels = Page.promote_panels + [
        FieldPanel("is_locked_for_references"),
    ]

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")


@register_setting(icon="globe-book")
class SiteConfig(ClusterableModel, BaseSiteSetting):
    # Branding
    logo = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Logo"),
        help_text=_("Site logo for light mode."),
    )
    logo_dark = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Logo (Dark)"),
        help_text=_("Site logo for dark mode."),
    )
    favicon = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Favicon"),
        help_text=_("Browser favicon for light mode."),
    )
    favicon_dark = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Favicon (Dark)"),
        help_text=_("Browser favicon for dark mode."),
    )

    # Open Graph
    og_image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Open Graph Image"),
        help_text=_(
            "Image displayed when sharing on social media in light mode."
            " Recommended size: 1200x630px"
        ),
    )
    og_image_dark = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Open Graph Image (Dark)"),
        help_text=_(
            "Image displayed when sharing on social media in dark mode."
            " Recommended size: 1200x630px"
        ),
    )

    # Admin Branding
    logo_admin = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Admin Logo"),
        help_text=_("Used as the main logo in the admin interface (light mode)."),
    )
    logo_admin_dark = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Admin Logo (Dark)"),
        help_text=_("Used as the main logo in the admin interface (dark mode)."),
    )
    symbol_admin = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Admin Symbol"),
        help_text=_(
            "Displayed as the small icon in admin areas like the sidebar (light mode)."
        ),
    )
    symbol_admin_dark = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("Admin Symbol (Dark)"),
        help_text=_(
            "Displayed as the small icon in admin areas like the sidebar (dark mode)."
        ),
    )

    # Theming
    font = models.ForeignKey(
        "phoxtail_design.FontFamily",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        help_text=_("Select a font for the site."),
    )

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    MultiFieldPanel(
                        [
                            FieldPanel("logo"),
                            FieldPanel("logo_dark"),
                        ],
                        heading=_("Logo"),
                    ),
                    MultiFieldPanel(
                        [
                            FieldPanel("favicon"),
                            FieldPanel("favicon_dark"),
                        ],
                        heading=_("Favicon"),
                        help_text=_(
                            "Favicons are small icons displayed in browser"
                            " tabs and bookmarks."
                        ),
                    ),
                ],
                heading=_("Branding"),
            ),
            ObjectList(
                [
                    MultiFieldPanel(
                        [
                            FieldPanel("og_image"),
                            FieldPanel("og_image_dark"),
                        ],
                        heading=_("Open Graph"),
                        help_text=_(
                            "Open Graph images are displayed when your site is"
                            " shared on social media platforms."
                        ),
                    ),
                ],
                heading=_("Social"),
            ),
            ObjectList(
                [
                    MultiFieldPanel(
                        [
                            FieldPanel("logo_admin"),
                            FieldPanel("logo_admin_dark"),
                            FieldPanel("symbol_admin"),
                            FieldPanel("symbol_admin_dark"),
                        ],
                        heading=_("Admin Branding"),
                    ),
                ],
                heading=_("Admin"),
            ),
            ObjectList(
                [
                    InlinePanel(
                        "fonts",
                        label=_("Font"),
                        heading=_("Typography"),
                        help_text=_(
                            "Assign fonts to semantic roles (e.g. heading, body, mono)."
                        ),
                    ),
                    InlinePanel(
                        "palettes",
                        label=_("Palette"),
                        heading=_("Color Palettes"),
                        help_text=_(
                            "Assign palettes to semantic roles"
                            " (e.g. surface, primary, accent)."
                        ),
                    ),
                ],
                heading=_("Theme"),
            ),
        ]
    )

    @property
    def css_variables(self):
        """Generate CSS custom properties for all configured design tokens."""
        css = []
        for sp in self.palettes.select_related("palette", "role").all():
            css.append(sp.get_css_variables())
        for sf in self.fonts.select_related("font_family", "role").all():
            css.append(sf.get_css_variables())
        return "\n".join(css)

    @property
    def font_face_declarations(self):
        """Generate @font-face declarations for configured fonts."""
        declarations = []
        for sf in self.fonts.select_related("font_family").all():
            declarations.append(sf.font_family.get_css_font_face_all())
        return "\n".join(declarations)

    class Meta:
        verbose_name = _("Site Config")
        verbose_name_plural = _("Site Configs")


class SiteConfigFont(Orderable, models.Model):
    """Links a FontFamily to a SiteConfig with a semantic role."""

    config = ParentalKey(SiteConfig, on_delete=models.CASCADE, related_name="fonts")
    font_family = models.ForeignKey(
        "phoxtail_design.FontFamily", on_delete=models.CASCADE, related_name="+"
    )
    role = models.ForeignKey(
        "phoxtail_design.FontRole",
        on_delete=models.PROTECT,
        related_name="+",
        help_text=_("Semantic role this font serves (e.g., heading, body)."),
    )

    class Meta(Orderable.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["config", "role"],
                name="unique_siteconfig_font_role",
            )
        ]

    def __str__(self):
        return f"{self.font_family} ({self.role.name})"

    def get_css_variables(self):
        """Generate CSS variables using the role identifier as namespace."""
        identifier = self.role.identifier
        css = [f"--font-{identifier}: {self.font_family.get_css_font_family()};"]
        css.append(self.font_family.get_weight_variables(identifier))
        return "\n".join(css)


class SiteConfigPalette(Orderable, models.Model):
    """Links a Palette to a SiteConfig with a semantic role."""

    config = ParentalKey(SiteConfig, on_delete=models.CASCADE, related_name="palettes")
    palette = models.ForeignKey(
        "phoxtail_design.Palette", on_delete=models.CASCADE, related_name="+"
    )
    role = models.ForeignKey(
        "phoxtail_design.PaletteRole",
        on_delete=models.PROTECT,
        related_name="+",
        help_text=_(
            "Semantic role this palette serves (e.g., surface, primary, accent)."
        ),
    )

    class Meta(Orderable.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["config", "role"],
                name="unique_siteconfig_role",
            )
        ]

    def __str__(self):
        return f"{self.palette} ({self.role.name})"

    def get_css_variables(self):
        """Generate CSS variables using the role identifier as namespace."""
        return self.palette.get_css_variables(self.role.identifier)
