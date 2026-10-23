"""A form field given alone: drawn in the field template built around its widget, else Django's own."""

import pytest
from django import forms
from django.template import Context, Template
from phonenumber_field.formfields import SplitPhoneNumberField

from phoxtail.core.fields import render_field


class EveryWidgetForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    notes = forms.CharField(widget=forms.Textarea)
    remember = forms.BooleanField()
    country = forms.ChoiceField(choices=[("gr", "Greece")])
    size = forms.ChoiceField(choices=[("s", "Small")], widget=forms.RadioSelect)
    days = forms.MultipleChoiceField(choices=[("mo", "Monday")], widget=forms.CheckboxSelectMultiple)
    phone = SplitPhoneNumberField()
    tags = forms.MultipleChoiceField(choices=[("a", "A")])
    starts_at = forms.SplitDateTimeField()


def _render(source, **context):
    return Template("{% load phoxtail_core_tags %}" + source).render(Context(context))


@pytest.mark.parametrize(
    ("field", "frame"),
    [
        ("email", "input"),
        ("password", "input"),
        ("notes", "textarea"),
        ("remember", "checkbox"),
        ("country", "select"),
        ("size", "choices"),
        ("days", "choices"),
        ("phone", "phone"),
    ],
)
def test_each_widget_gets_the_field_built_around_it(field, frame):
    form = EveryWidgetForm()

    assert _render("{% field bound_field %}", bound_field=form[field]) == render_field(frame, form[field])


@pytest.mark.parametrize("field", ["tags", "starts_at"])
def test_a_widget_no_field_draws_is_drawn_django_s_way(field):
    form = EveryWidgetForm()

    assert _render("{% field bound_field %}", bound_field=form[field]) == form[field].as_field_group()


def test_options_reach_the_field_picked():
    form = EveryWidgetForm()

    assert _render("{% field form.email autofocus=True %}", form=form) == render_field(
        "input", form["email"], autofocus=True
    )


def test_an_option_the_field_picked_does_not_take_is_refused():
    with pytest.raises(TypeError, match="the 'select' field has no option autofocus"):
        _render("{% field form.country autofocus=True %}", form=EveryWidgetForm())


def test_options_for_a_widget_no_field_draws_are_refused():
    with pytest.raises(TypeError, match="no field template draws 'tags' .SelectMultiple., so it takes no options"):
        _render("{% field form.tags show_label=False %}", form=EveryWidgetForm())


def test_a_misspelled_form_field_is_named_as_such():
    with pytest.raises(TypeError, match="{% field %} needs a form field, got ''; check the spelling"):
        _render("{% field form.emial %}", form=EveryWidgetForm())


def test_a_named_field_is_drawn_as_before():
    form = EveryWidgetForm()

    assert _render('{% field "input" form.email %}', form=form) == render_field("input", form["email"])
