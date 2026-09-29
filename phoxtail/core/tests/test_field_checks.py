"""The system check reads every template's `{% field %}` calls at startup."""

import pytest
from django.conf import settings
from django.test import override_settings

from phoxtail.core.checks import field_calls

LOAD = "{% load phoxtail_core_tags %}\n"


@pytest.fixture
def site_template(tmp_path):
    """Write one template into a project folder the check reads, and run the check."""

    def check(source):
        (tmp_path / "page.html").write_text(source)
        with override_settings(TEMPLATES=[{**settings.TEMPLATES[0], "DIRS": [tmp_path]}]):
            return [(error.id, error.msg) for error in field_calls(None)]

    return check


def test_every_installed_template_passes():
    assert field_calls(None) == []


def test_a_correct_call_passes(site_template):
    assert site_template(LOAD + '{% field "input" form.email show_label=False hx_get=url %}') == []


def test_a_misspelled_option_is_reported_with_its_place(site_template):
    [(id, msg)] = site_template(LOAD + '\n{% field "input" form.email show_lable=False %}')

    assert id == "phoxtail_core.E002"
    assert "page.html, line 3" in msg
    assert "has no option show_lable; its options are" in msg


def test_an_unknown_field_is_reported(site_template):
    [(id, msg)] = site_template(LOAD + '{% field "inptu" form.email %}')

    assert id == "phoxtail_core.E002"
    assert "there is no 'inptu' field" in msg


def test_a_part_of_a_field_is_reported(site_template):
    [(_, msg)] = site_template(LOAD + '{% field "single_select_search/input" form.user %}')

    assert "is not a field name" in msg


def test_a_template_that_does_not_load_the_tag_is_reported(site_template):
    [(id, msg)] = site_template('{% field "input" form.email %}')

    assert id == "phoxtail_core.E001"
    assert "field" in msg


def test_a_call_inside_a_comment_is_not_checked(site_template):
    assert site_template(LOAD + '{% comment %}{% field "inptu" form.email %}{% endcomment %}') == []


def test_a_name_held_in_a_variable_is_left_to_the_draw(site_template):
    assert site_template(LOAD + "{% field name form.email show_lable=False %}") == []


def test_a_template_with_a_relative_include_is_read(site_template):
    """A relative name resolves against the template's own name, as its loader gives it."""
    source = LOAD + '{% include "./part.html" %}{% field "input" form.email show_lable=False %}'

    [(id, _)] = site_template(source)

    assert id == "phoxtail_core.E002"


def test_a_call_by_keyword_is_checked(site_template):
    [(_, msg)] = site_template(LOAD + '{% field name="input" bound_field=form.email show_lable=False %}')

    assert "has no option show_lable" in msg
