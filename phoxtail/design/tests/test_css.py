"""Text people saved cannot end the <style> every page carries.

The site's fonts and palettes reach every page, the login page included,
through ``phoxtail_core/stylesheets.html``: a ``<style>`` built from font
names, fallback lists and role identifiers. A browser ends that element at
the first ``</style``, so a font named ``Inter</style><script>…`` would run
its script for every visitor. Two locks: each value is escaped where the CSS
is built, which also covers rows saved before the rules existed; and the
models refuse such values, so a person gets an error instead.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.test import RequestFactory

from phoxtail.design import css
from phoxtail.design.models import FontFamily, FontRole, FontWeight, Palette, PaletteRole, PaletteSet

HOSTILE = 'Inter</style><script>alert(1)</script>"\\\n'


class TestString:
    def test_nothing_in_it_can_end_the_style_or_the_string(self):
        written = css.string(HOSTILE)

        assert "<" not in written
        assert "\n" not in written
        assert written == '"Inter\\3c /style>\\3c script>alert(1)\\3c /script>\\"\\\\\\a "'

    def test_a_plain_name_reads_as_itself(self):
        assert css.string("Source Sans 3") == '"Source Sans 3"'


class TestName:
    def test_only_letters_digits_hyphens_and_underscores_stay_as_they_are(self):
        assert css.name("heading_2-alt") == "heading_2-alt"
        assert css.name("x;}</style>") == "x\\3b \\7d \\3c \\2f style\\3e "


class TestFontFamily:
    def test_a_fallback_list_keeps_its_generic_families_bare(self):
        """Quoted, "serif" would be a font named serif, not the generic one."""
        written = css.font_family("Cormorant Garamond", "Georgia, 'Times New Roman', Times, serif")

        assert written == '"Cormorant Garamond", Georgia, "Times New Roman", Times, serif'

    def test_a_name_with_spaces_is_quoted_whether_or_not_it_was(self):
        assert css.font_family("Inter", 'system-ui, -apple-system, Segoe UI, "Helvetica Neue"') == (
            '"Inter", system-ui, -apple-system, "Segoe UI", "Helvetica Neue"'
        )

    def test_a_hostile_fallback_stays_inside_its_strings(self):
        written = css.font_family("Inter", "serif; } body { display: none } </style><script>")

        # One string, the whole item: its ";" and "}" are letters in a name.
        assert written == '"Inter", "serif; } body { display: none } \\3c /style>\\3c script>"'


class TestValidators:
    @pytest.mark.parametrize("name", ["Inter", "Source Sans 3", "M PLUS 1p", "Noto Sans JP", "Playfair-Display"])
    def test_real_font_names_pass(self, name):
        css.validate_font_name(name)

    @pytest.mark.parametrize(
        "name", [HOSTILE, "Inter'", 'Inter"', "Inter;", "Inter, serif", "Inter\n", " Inter", "Inter_Display"]
    )
    def test_a_name_that_could_leave_its_string_is_refused(self, name):
        with pytest.raises(ValidationError):
            css.validate_font_name(name)

    @pytest.mark.parametrize(
        "fallback",
        [
            "system-ui, -apple-system, sans-serif",
            "Georgia, 'Times New Roman', Times, serif",
            'ui-monospace, "Cascadia Code", monospace',
        ],
    )
    def test_real_fallback_lists_pass(self, fallback):
        css.validate_fallback(fallback)

    @pytest.mark.parametrize("fallback", ["serif; color: red", "'Times New Roman", "serif</style>", "a,,b"])
    def test_a_fallback_that_is_not_a_list_of_names_is_refused(self, fallback):
        with pytest.raises(ValidationError):
            css.validate_fallback(fallback)

    @pytest.mark.parametrize("identifier", ["a b", "x;}", "</style>"])
    def test_an_identifier_must_be_a_slug(self, identifier):
        with pytest.raises(ValidationError):
            css.validate_identifier(identifier)


@pytest.mark.django_db
class TestModels:
    def test_the_models_refuse_what_the_rules_refuse(self):
        family = FontFamily(name=HOSTILE, fallback="serif; }")
        role = FontRole(name="Heading", identifier="x;}", description="Headings.")
        palette_role = PaletteRole(name="Primary", identifier="a b", description="Buttons.")

        with pytest.raises(ValidationError) as family_error:
            family.full_clean()
        with pytest.raises(ValidationError) as role_error:
            role.full_clean()
        with pytest.raises(ValidationError) as palette_role_error:
            palette_role.full_clean()

        assert set(family_error.value.message_dict) == {"name", "fallback"}
        assert set(role_error.value.message_dict) == {"identifier"}
        assert set(palette_role_error.value.message_dict) == {"identifier"}

    def test_the_admin_swatches_escape_their_colours(self):
        """Saved through the ORM, a colour skips the hex check; the list escapes it."""
        palette_set = PaletteSet.objects.create(name="Set", identifier="set")
        shades = {f"shade_{s}": "#000000" for s in (50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950)}
        palette = Palette.objects.create(palette_set=palette_set, title="Blue", **{**shades, "shade_50": '#"><b>'})

        assert "<b>" not in palette.shades_preview()
        assert "&quot;&gt;&lt;b&gt;" in palette.shades_preview()


@pytest.mark.django_db
def test_a_hostile_row_saved_before_the_rules_renders_harmlessly():
    """The ORM skips validators, as a row saved before them would have."""
    from wagtail.models import Site

    from phoxtail.cms.models import SiteSetting, SiteSettingFont

    site = Site.objects.get(is_default_site=True)
    family = FontFamily.objects.create(name=HOSTILE, fallback="serif; } </style><script>")
    FontWeight.objects.create(family=family, weight=400, file=ContentFile(b"wOF2", name="inter.woff2"))
    role = FontRole.objects.create(name="Heading", identifier="</style><script>", description="Headings.")
    SiteSettingFont.objects.create(config=SiteSetting.for_site(site), font_family=family, role=role)

    request = RequestFactory().get("/", HTTP_HOST=site.hostname)
    html = render_to_string("phoxtail_core/stylesheets.html", {"request": request})

    style = html[html.index("<style>") + len("<style>") : html.index("</style>")]
    assert html.count("</style>") == 1
    assert "<" not in style
    assert "--font-\\3c \\2f style\\3e \\3c script\\3e :" in style
    # Marked safe where it is built: the template does not turn its quotes
    # into HTML entities, which a <style> would not read back.
    assert 'font-family: "Inter\\3c /style>' in style


@pytest.mark.django_db
class TestAdminForms:
    """The admin's forms run the models' validators on the fields people type."""

    def test_the_font_family_form_refuses_a_hostile_name_and_fallback(self):
        from phoxtail.design.viewsets import FontFamilyViewSet

        form_class = FontFamilyViewSet().get_form_class()
        form = form_class(
            data={
                "name": HOSTILE,
                "category": "sans-serif",
                "fallback": "serif; }",
                "description": "",
                "weights-TOTAL_FORMS": "0",
                "weights-INITIAL_FORMS": "0",
            },
            instance=FontFamily(),
        )

        assert not form.is_valid()
        assert {"name", "fallback"} <= set(form.errors)

    @pytest.mark.parametrize("viewset", ["FontRoleViewSet", "PaletteRoleViewSet"])
    def test_a_role_form_refuses_a_hostile_identifier(self, viewset):
        from phoxtail.design import viewsets

        view_set = getattr(viewsets, viewset)()
        form = view_set.get_form_class()(
            data={"name": "Heading", "identifier": "</style>", "description": "Headings."},
            instance=view_set.model(),
        )

        assert not form.is_valid()
        assert set(form.errors) == {"identifier"}
