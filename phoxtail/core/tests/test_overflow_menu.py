import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.template import TemplateSyntaxError, engines
from django.template.loader import render_to_string


def render(source, **context):
    return engines["django"].from_string("{% load phoxtail_core_tags %}" + source).render(context)


ITEM = '<button type="button" class="phx-overflow-menu__item">Edit</button>'


def test_the_button_opens_the_menu_beside_it():
    html = render("{% overflow_menu %}" + ITEM + "{% endoverflow_menu %}")

    menu_id = re.search(r'popovertarget="([^"]+)"', html).group(1)
    assert f'id="{menu_id}"' in html
    assert 'class="phx-overflow-menu__list phx-popover"' in html
    assert 'data-popover-placement="bottom-end"' in html
    assert re.search(r"<div[^>]*\bpopover\b", html)
    assert 'aria-label="More actions"' in html
    assert "icon-more-vert" in html
    assert ITEM in html


def test_no_rows_no_button():
    """Every row left out (a permission, a state) leaves no ⋮ to open an empty menu."""
    assert render("{% overflow_menu %}{% if False %}" + ITEM + "{% endif %}  {% endoverflow_menu %}") == ""


def test_each_menu_has_an_id_of_its_own():
    """A drawer at each level can show one: their buttons must not open each other's."""
    menu = "{% overflow_menu %}" + ITEM + "{% endoverflow_menu %}"
    html = render(menu + menu)

    ids = re.findall(r'popovertarget="([^"]+)"', html)
    assert len(set(ids)) == 2


def test_label_placement_and_id_are_the_callers():
    html = render(
        '{% overflow_menu label=name placement="top-start" id="row-7" %}' + ITEM + "{% endoverflow_menu %}",
        name="More actions for Ann & Bo",
    )

    assert 'aria-label="More actions for Ann &amp; Bo"' in html
    assert 'data-popover-placement="top-start"' in html
    assert 'popovertarget="row-7"' in html
    assert 'id="row-7"' in html


def test_the_label_can_be_translated_in_place():
    html = render('{% load i18n %}{% overflow_menu label=_("More actions") %}' + ITEM + "{% endoverflow_menu %}")

    assert 'aria-label="More actions"' in html


def test_the_label_is_translated_by_default():
    from django.utils.translation import override

    with override("el"):
        html = render("{% overflow_menu %}" + ITEM + "{% endoverflow_menu %}")

    assert 'aria-label="Περισσότερες ενέργειες"' in html


def test_a_placement_popover_js_does_not_know_fails_loudly():
    with pytest.raises(TemplateSyntaxError, match="placement"):
        render('{% overflow_menu placement="below" %}' + ITEM + "{% endoverflow_menu %}")


@pytest.mark.parametrize("options", ['colour="red"', '"More"'])
def test_only_its_named_options_are_taken(options):
    with pytest.raises(TemplateSyntaxError):
        render("{% overflow_menu " + options + " %}" + ITEM + "{% endoverflow_menu %}")


def _static(path):
    return Path(finders.find(f"phoxtail_core/{path}")).read_text()


def test_every_page_with_core_loads_the_placement_and_the_menu():
    assert "phoxtail_core/js/popover.js" in render_to_string("phoxtail_core/scripts.html")
    stylesheets = Path(__file__).parents[1] / "templates/phoxtail_core/stylesheets.html"
    assert "phoxtail_core/css/components/overflow_menu.css" in stylesheets.read_text()
    assert finders.find("phoxtail_core/css/components/overflow_menu.css")


def test_placement_is_opt_in():
    """Only a popover that asks for it (data-popover-placement) is placed and
    closed by popover.js: a .phx-popover is otherwise only a look."""
    script = _static("js/popover.js")
    assert "var PLACED = '.phx-popover[popover][data-popover-placement]';" in script
    assert ".phx-popover[popover][data-popover-placement] {" in _static("css/components/surfaces.css")


def test_the_script_knows_every_placement_the_tag_allows():
    from phoxtail.core.templatetags.phoxtail_core_tags import POPOVER_PLACEMENTS

    script = _static("js/popover.js")
    assert "var SIDES = {top: 'bottom', bottom: 'top', left: 'right', right: 'left'};" in script
    assert {p.split("-")[0] for p in POPOVER_PLACEMENTS} == {"top", "bottom", "left", "right"}
    assert {p.split("-")[1] for p in POPOVER_PLACEMENTS} == {"start", "end"}


def test_start_and_end_follow_the_text_direction():
    """As CSS's start and end: above or below its button, a menu lined up
    with its start edge lines up with the right one in a right-to-left page."""
    script = _static("js/popover.js")
    assert "var leftEdge = start !== (getComputedStyle(button).direction === 'rtl');" in script


def test_a_resize_places_it_again_and_a_hidden_button_closes_it():
    """A phone's address bar resizes the window: the menu stays, placed
    again; a button no longer shown leaves it nowhere to be, so it closes."""
    script = _static("js/popover.js")
    assert "document.querySelectorAll(PLACED + ':popover-open').forEach(place);" in script
    assert "if (!button.isConnected || !button.getClientRects().length) {" in script


def test_the_offset_is_read_in_pixels():
    """Registered as a length, so a rem or calc() reaches the script as px."""
    css = _static("css/components/surfaces.css")
    assert '@property --phx-popover-offset {\n    syntax: "<length>";' in css


def test_the_button_shares_the_close_buttons_look():
    css = _static("css/modal.css")
    assert ".phoxtail-close-btn,\n.phx-overflow-menu__button {\n    flex-shrink: 0;" in css
