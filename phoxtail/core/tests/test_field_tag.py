"""`{% field %}` draws a core field template from the values it is given."""

import pytest
from django import forms
from django.template import Context, Template, TemplateDoesNotExist

from phoxtail.core.fields import render_field


class ContactForm(forms.Form):
    email = forms.EmailField(label="Email address")


def _render(source, **context):
    return Template("{% load phoxtail_core_tags %}" + source).render(Context(context))


def test_the_named_template_draws_the_bound_field():
    html = _render('{% field "input" form.email %}', form=ContactForm())

    assert 'name="email"' in html
    assert 'type="email"' in html
    assert "Email address" in html


def test_values_passed_to_the_tag_reach_the_template():
    html = _render('{% field "input" form.email show_label=False %}', form=ContactForm())

    assert "Email address" not in html


def test_the_page_values_do_not_reach_the_template():
    """A value set higher up the page must not change a field that did not ask for it."""
    html = _render('{% field "input" form.email %}', form=ContactForm(), show_label=False)

    assert "Email address" in html


def test_the_field_is_drawn_by_django_like_its_own_field_templates():
    """Django's form renderer draws it, so a page's escaping switch does not reach it."""
    form = ContactForm()
    tag = '{% field "input" form.email label=label %}'

    html = _render("{% autoescape off %}" + tag + "{% endautoescape %}", form=form, label="<b>Email</b>")

    assert html == form["email"].render(
        "phoxtail_core/forms/widgets/input.html", {"field": form["email"], "label": "<b>Email</b>"}
    )
    assert "&lt;b&gt;Email&lt;/b&gt;" in html


def test_an_unknown_field_name_fails_loudly():
    with pytest.raises(TemplateDoesNotExist):
        _render('{% field "no_such_field" form.email %}', form=ContactForm())


@pytest.mark.parametrize("name", ["htmx/select", "single_select_search/input", "../input", "Input"])
def test_only_whole_fields_are_drawn(name):
    """A folder holds a field's parts, which are drawn by the field, never on their own."""
    with pytest.raises(ValueError, match="is not a field name"):
        _render("{% field name form.email %}", name=name, form=ContactForm())


def test_a_misspelled_form_field_fails_loudly():
    """Django turns an unknown variable into "", which would draw an input with no name."""
    with pytest.raises(TypeError, match="needs a form field"):
        _render('{% field "input" form.emial %}', form=ContactForm())


def test_a_view_draws_a_field_the_same_way_as_the_tag():
    form = ContactForm()

    assert render_field("input", form["email"], show_label=False) == _render(
        '{% field "input" form.email show_label=False %}', form=form
    )
