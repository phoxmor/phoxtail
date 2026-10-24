from django.db import models
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.models import Orderable
from wagtail.search import index
from wagtail_color_panel.fields import ColorField

from phoxtail.core.mixins import TimestampMixin, UUIDMixin
from phoxtail.design import css


class FontFamily(index.Indexed, UUIDMixin, TimestampMixin, ClusterableModel):
    """A font family with multiple weights/styles"""

    name = models.CharField(
        max_length=100,
        unique=True,
        validators=[css.validate_font_name],
        help_text=_("Font family name as it appears in CSS (e.g., 'Inter', 'Roboto')"),
        verbose_name=_("name"),
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Optional description of the font and its intended use"),
        verbose_name=_("description"),
    )
    category = models.CharField(
        max_length=50,
        choices=[
            ("serif", _("Serif")),
            ("sans-serif", _("Sans Serif")),
            ("monospace", _("Monospace")),
            ("display", _("Display")),
            ("handwriting", _("Handwriting")),
        ],
        default="sans-serif",
        help_text=_("Font category - helps with fallback selection and appropriate usage"),
        verbose_name=_("category"),
    )
    fallback = models.CharField(
        max_length=255,
        blank=True,
        default="system-ui, -apple-system, sans-serif",
        validators=[css.validate_fallback],
        help_text=_("CSS fallback fonts (e.g., 'system-ui, -apple-system, sans-serif')"),
        verbose_name=_("fallback"),
    )

    search_fields = [
        index.AutocompleteField("name"),
    ]

    class Meta:
        verbose_name = _("Font Family")
        verbose_name_plural = _("Font Families")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_css_font_family(self):
        """Return the complete font-family CSS value with fallbacks"""
        return css.font_family(self.name, self.fallback)

    def get_css_font_face_all(self):
        """Generate @font-face declarations for all weights"""
        declarations = []
        for weight in self.weights.all():
            declarations.append(weight.get_css_font_face())
        return "\n".join(declarations)

    def get_available_weights(self):
        """Return list of available weight values"""
        return list(self.weights.values_list("weight", flat=True))

    def get_nearest_weight(self, target_weight):
        """Find the closest available weight to the target."""
        available = self.get_available_weights()
        if not available:
            return target_weight
        return min(available, key=lambda x: abs(x - target_weight))

    def get_weight_variables(self, role_identifier):
        """Generate semantic weight variables for a specific role."""
        semantic_weights = {
            "thin": 100,
            "light": 300,
            "regular": 400,
            "medium": 500,
            "semibold": 600,
            "bold": 700,
            "extrabold": 800,
            "black": 900,
        }
        vars = []
        for name, value in semantic_weights.items():
            best_match = self.get_nearest_weight(value)
            vars.append(f"--font-{css.name(role_identifier)}-weight-{name}: {int(best_match)};")
        return "\n".join(vars)


class FontWeight(index.Indexed, UUIDMixin, TimestampMixin, Orderable, models.Model):
    """A specific weight/style variant of a font family"""

    family = ParentalKey(FontFamily, on_delete=models.CASCADE, related_name="weights", verbose_name=_("family"))
    weight = models.PositiveIntegerField(
        default=400,
        help_text=_("Font weight value (100=Thin, 400=Regular, 700=Bold, 900=Black)"),
        verbose_name=_("weight"),
    )
    style = models.CharField(
        max_length=20,
        choices=[
            ("normal", _("Normal")),
            ("italic", _("Italic")),
        ],
        default="normal",
        help_text=_("Font style"),
        verbose_name=_("style"),
    )
    file = models.FileField(
        upload_to="fonts/", help_text=_("WOFF2 font file (convert TTF/OTF to WOFF2 first)"), verbose_name=_("file")
    )

    class Meta(Orderable.Meta):
        verbose_name = _("Font Weight")
        verbose_name_plural = _("Font Weights")
        constraints = [
            models.UniqueConstraint(
                fields=["family", "weight", "style"],
                name="unique_family_weight_style",
            )
        ]

    def __str__(self):
        style_suffix = f" {self.style.title()}" if self.style != "normal" else ""
        return f"{self.family.name} {self.weight}{style_suffix}"

    def get_css_font_face(self):
        """Generate @font-face CSS for this weight"""
        if not self.file:
            return ""

        style = self.style if self.style in ("normal", "italic") else "normal"
        return f"""@font-face {{
    font-family: {css.string(self.family.name)};
    src: {css.url(self.file.url)} format('woff2');
    font-weight: {int(self.weight)};
    font-style: {style};
    font-display: swap;
}}"""


class FontRole(index.Indexed, models.Model):
    """Semantic role for a font within a design system"""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Display name (e.g., 'Heading', 'Body', 'Monospace')"),
        verbose_name=_("name"),
    )
    identifier = models.CharField(
        max_length=50,
        unique=True,
        validators=[css.validate_identifier],
        help_text=_("CSS namespace identifier (e.g., 'heading'). Used as prefix in CSS variables: --font-{identifier}"),
        verbose_name=_("identifier"),
    )
    description = models.TextField(
        help_text=_("Describes the semantic purpose of this font role."), verbose_name=_("description")
    )

    search_fields = [
        index.AutocompleteField("name"),
        index.AutocompleteField("identifier"),
    ]

    class Meta:
        verbose_name = _("Font Role")
        verbose_name_plural = _("Font Roles")
        ordering = ["name"]

    def __str__(self):
        return self.name


class PaletteRole(index.Indexed, models.Model):
    """Semantic role for a palette within a design system"""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Display name (e.g., 'Surface', 'Primary', 'Accent')"),
        verbose_name=_("name"),
    )
    identifier = models.CharField(
        max_length=50,
        unique=True,
        validators=[css.validate_identifier],
        help_text=_(
            "CSS namespace identifier (e.g., 'surface'). Used as prefix in CSS variables: --color-{identifier}-{shade}"
        ),
        verbose_name=_("identifier"),
    )
    description = models.TextField(
        help_text=(
            _(
                "Describes the semantic purpose of this role and how its shades "
                "map to light/dark mode (e.g., shade-50 for light backgrounds, "
                "shade-950 for dark backgrounds)."
            )
        ),
        verbose_name=_("description"),
    )

    search_fields = [
        index.AutocompleteField("name"),
        index.AutocompleteField("identifier"),
    ]

    class Meta:
        verbose_name = _("Palette Role")
        verbose_name_plural = _("Palette Roles")
        ordering = ["name"]

    def __str__(self):
        return self.name


class PaletteSet(index.Indexed, UUIDMixin, TimestampMixin, Orderable, ClusterableModel):
    """A named grouping of palettes (e.g., 'Tailwind', 'Spring', 'Autumn')."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Human-readable name (e.g., 'Tailwind', 'Spring')"),
        verbose_name=_("name"),
    )
    identifier = models.CharField(
        max_length=50,
        unique=True,
        help_text=_("Slug-style identifier matching the filesystem group directory"),
        verbose_name=_("identifier"),
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text=_("Optional description of the palette set's purpose or theme"),
        verbose_name=_("description"),
    )

    search_fields = [
        index.AutocompleteField("name"),
        index.AutocompleteField("identifier"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Palette Set")
        verbose_name_plural = _("Palette Sets")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Palette(index.Indexed, UUIDMixin, TimestampMixin, Orderable, models.Model):
    """A color palette with shades from 50 to 950"""

    palette_set = ParentalKey(
        PaletteSet, on_delete=models.CASCADE, related_name="palettes", verbose_name=_("palette set")
    )
    title = models.CharField(
        max_length=100, help_text=_("Name of the palette (e.g., 'red', 'custom_blue')"), verbose_name=_("title")
    )
    description = models.TextField(
        blank=True, default="", help_text=_("Optional description of the palette"), verbose_name=_("description")
    )
    shade_50 = ColorField(help_text=_("Hex color for shade 50 (lightest)"), verbose_name=_("shade 50"))
    shade_100 = ColorField(help_text=_("Hex color for shade 100"), verbose_name=_("shade 100"))
    shade_200 = ColorField(help_text=_("Hex color for shade 200"), verbose_name=_("shade 200"))
    shade_300 = ColorField(help_text=_("Hex color for shade 300"), verbose_name=_("shade 300"))
    shade_400 = ColorField(help_text=_("Hex color for shade 400"), verbose_name=_("shade 400"))
    shade_500 = ColorField(help_text=_("Hex color for shade 500 (base)"), verbose_name=_("shade 500"))
    shade_600 = ColorField(help_text=_("Hex color for shade 600"), verbose_name=_("shade 600"))
    shade_700 = ColorField(help_text=_("Hex color for shade 700"), verbose_name=_("shade 700"))
    shade_800 = ColorField(help_text=_("Hex color for shade 800"), verbose_name=_("shade 800"))
    shade_900 = ColorField(help_text=_("Hex color for shade 900"), verbose_name=_("shade 900"))
    shade_950 = ColorField(help_text=_("Hex color for shade 950 (darkest)"), verbose_name=_("shade 950"))

    search_fields = [
        index.SearchField("title"),
        index.SearchField("description"),
        index.AutocompleteField("title"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Palette")
        verbose_name_plural = _("Palettes")
        constraints = [
            models.UniqueConstraint(
                fields=["palette_set", "title"],
                name="unique_palette_set_title",
            )
        ]

    def __str__(self):
        return self.title

    def hex_to_rgb_string(self, hex_color):
        """Convert hex color to RGB string format for CSS variables"""
        if not hex_color:
            return "0 0 0"

        hex_color = hex_color.lstrip("#")

        if len(hex_color) == 3:
            hex_color = "".join([char * 2 for char in hex_color])

        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r} {g} {b}"
        except (ValueError, IndexError):
            return "0 0 0"

    def get_rgb_shade(self, shade_number):
        """Get RGB string for a specific shade number"""
        shade_field = f"shade_{shade_number}"
        hex_value = getattr(self, shade_field, None)
        return self.hex_to_rgb_string(hex_value)

    def get_css_variables(self, color_name="primary"):
        """Generate CSS variables string for all shades in RGB format"""
        shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]
        css_vars = []

        for shade in shades:
            rgb_value = self.get_rgb_shade(shade)
            css_vars.append(f"--color-{css.name(color_name)}-{shade}: {rgb_value};")

        return "\n".join(css_vars)

    def get_all_shades_rgb(self):
        """Get all shades as a dictionary with RGB values"""
        shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]
        return {shade: self.get_rgb_shade(shade) for shade in shades}

    @property
    def shades_rgb(self):
        """Dict with string keys for DTL dot-lookup: {{ palette.shades_rgb.50 }}"""
        shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]
        return {str(shade): self.get_rgb_shade(shade) for shade in shades}

    def get_all_shades_hex(self):
        """Get all shades as a dictionary with hex values"""
        shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]
        return {shade: getattr(self, f"shade_{shade}") for shade in shades}

    def shades_preview(self):
        """Display square, rounded boxes of all shades in the admin list view."""
        shades = [
            (self.shade_50, "50"),
            (self.shade_100, "100"),
            (self.shade_200, "200"),
            (self.shade_300, "300"),
            (self.shade_400, "400"),
            (self.shade_500, "500"),
            (self.shade_600, "600"),
            (self.shade_700, "700"),
            (self.shade_800, "800"),
            (self.shade_900, "900"),
            (self.shade_950, "950"),
        ]
        return format_html_join(
            "",
            '<span style="display: inline-block; width: 1.5rem; height: 1.5rem; '
            "border-radius: 0.375rem; border: 1px solid #a3a3a3; margin-right: 4px; "
            'background-color: {};" title="{}"></span>',
            shades,
        )

    # Wagtail reads the label off the function object; a type checker sees
    # only the callable.
    shades_preview.short_description = _("Shades")  # type: ignore[attr-defined]
