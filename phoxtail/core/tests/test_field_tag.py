"""`{% field %}` draws a core field template from the values it is given."""

import datetime
import decimal
from pathlib import Path

import pytest
from django import forms
from django.forms.renderers import get_default_renderer
from django.template import Context, Template, TemplateDoesNotExist
from django.utils import translation

from phoxtail.core import fields
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
        "phoxtail_core/forms/fields/input.html", {"field": form["email"], "label": "<b>Email</b>"}
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


class EventForm(forms.Form):
    title = forms.CharField()
    status = forms.ChoiceField(choices=[("draft", "Draft"), ("live", "Live")])
    seats = forms.IntegerField()
    starts = forms.DateTimeField()


MERGED = [("input", "title"), ("input", "seats"), ("select", "status"), ("input", "starts")]


@pytest.mark.parametrize(("name", "form_field"), MERGED)
def test_hx_get_makes_the_field_talk_to_the_server(name, form_field):
    html = render_field(name, EventForm()[form_field], hx_get="/search/", hx_target="#results")

    assert 'hx-get="/search/"' in html
    assert 'hx-target="#results"' in html
    assert 'hx-swap="innerHTML"' in html
    assert 'hx-trigger="change"' in html


@pytest.mark.parametrize(("name", "form_field"), MERGED)
def test_an_explicit_swap_and_trigger_win_over_the_defaults(name, form_field):
    html = render_field(name, EventForm()[form_field], hx_get="/search/", hx_swap="outerHTML", hx_trigger="input")

    assert 'hx-swap="outerHTML"' in html
    assert 'hx-trigger="input"' in html


@pytest.mark.parametrize(("name", "form_field"), MERGED)
def test_without_hx_get_the_field_is_plain(name, form_field):
    """Settings without a request to make would be inert; the field writes none of them."""
    html = render_field(name, EventForm()[form_field], hx_target="#results", hx_swap="outerHTML")

    assert "hx-" not in html


FIELD_FILES = sorted(
    path.relative_to(Path(fields.__file__).parent / "templates").as_posix()
    for path in (Path(fields.__file__).parent / "templates" / fields.FIELD_TEMPLATES).rglob("*.html")
)


@pytest.mark.parametrize("template_name", FIELD_FILES)
def test_every_field_template_loads_through_the_form_renderer(template_name):
    """Fields are drawn by the form renderer, not the page's engine; each file, parts included, must load there."""
    get_default_renderer().get_template(template_name)


class ProfileForm(forms.Form):
    nickname = forms.CharField(
        max_length=20, help_text="Shown to others", widget=forms.TextInput(attrs={"autocomplete": "nickname"})
    )
    price = forms.DecimalField(initial=decimal.Decimal("1234.5"))


def test_django_draws_the_input_with_what_the_form_declares():
    html = render_field("input", ProfileForm()["nickname"])

    assert 'maxlength="20"' in html
    assert 'autocomplete="nickname"' in html
    assert "required" in html
    assert 'class="fw-md3-control"' in html
    assert 'placeholder=" "' in html


def test_a_number_keeps_its_decimal_point_in_every_language():
    """A number input cannot read "1234,5"; Django's widget writes the value unlocalised."""
    with translation.override("el"):
        html = render_field("input", ProfileForm()["price"])

    assert 'type="number"' in html
    assert 'value="1234.5"' in html


def test_the_control_points_at_the_help_text_by_djangos_ids():
    html = render_field("input", ProfileForm()["nickname"])

    assert 'aria-describedby="id_nickname_helptext"' in html
    assert 'id="id_nickname_helptext"' in html


def test_errors_take_the_help_texts_place_under_the_field():
    form = ProfileForm(data={"nickname": ""})
    html = render_field("input", form["nickname"])

    assert 'aria-describedby="id_nickname_helptext id_nickname_error"' in html
    assert 'id="id_nickname_error"' in html
    assert "Shown to others" not in html


def test_input_type_overrides_the_widget_type_without_changing_the_form():
    form = ProfileForm()
    html = render_field("input", form["nickname"], input_type="url")

    assert 'type="url"' in html
    assert form["nickname"].field.widget.input_type == "text"


def test_a_zero_attribute_is_kept():
    """0 == False in Python; a caller asking for tabindex=0 must still get it."""
    html = render_field("input", ProfileForm()["nickname"])
    assert 'tabindex="0"' in fields.render_control(ProfileForm()["nickname"], tabindex=0)
    assert "tabindex" not in html


def test_a_form_without_ids_gets_no_empty_ids():
    html = render_field("input", ProfileForm(auto_id=False)["nickname"])

    assert "_helptext" not in html
    assert "_error" not in html


def test_any_htmx_setting_reaches_the_input():
    html = render_field("input", ProfileForm()["nickname"], hx_post="/save/", hx_indicator="#spin", hx_confirm="Sure?")

    assert 'hx-post="/save/"' in html
    assert 'hx-indicator="#spin"' in html
    assert 'hx-confirm="Sure?"' in html
    assert 'hx-trigger="change"' in html


def test_htmx_settings_without_a_request_are_not_written():
    html = render_field("input", ProfileForm()["nickname"], hx_indicator="#spin", hx_target="#x")

    assert "hx-" not in html


class SecretForm(forms.Form):
    secret = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


def test_the_password_field_never_writes_the_typed_value_back():
    """A form re-shown with errors must not put the password into the page."""
    html = render_field("input", SecretForm(data={"secret": "hunter2", "other": "x"})["secret"])

    assert 'type="password"' in html
    assert 'autocomplete="current-password"' in html
    assert "hunter2" not in html


def test_the_password_toggle_carries_no_script_of_its_own():
    """The toggle lives once in js/fields.js, so a page with two password fields has no repeated code."""
    html = render_field("input", SecretForm()["secret"])

    assert "<script" not in html
    assert "onclick" not in html
    assert "data-password-toggle" in html


def test_the_shared_scripts_load_the_field_behaviour():
    from django.template.loader import render_to_string

    assert "phoxtail_core/js/fields.js" in render_to_string("phoxtail_core/scripts.html")


def test_the_password_toggle_is_a_labelled_toggle_button():
    """One constant label; aria-pressed tells a screen reader whether the password is shown."""
    html = render_field("input", SecretForm()["secret"])

    assert 'aria-label="Show password"' in html
    assert 'aria-pressed="false"' in html


def test_quotes_in_a_template_written_option_do_not_break_the_attribute():
    """Template string literals are marked safe; their quotes must still be escaped in the attribute."""
    html = _render(
        """{% field "input" form.email hx_get="/x/" hx_vals='js:{a: document.getElementById("id_b").value}' %}""",
        form=ContactForm(),
    )

    assert 'hx-vals="js:{a: document.getElementById(&quot;id_b&quot;).value}"' in html


def test_a_value_from_a_variable_is_escaped_only_once():
    html = _render('{% field "input" form.email placeholder=ph %}', form=ContactForm(), ph="a&b")

    assert 'placeholder="a&amp;b"' in html


def test_a_number_is_drawn_by_the_input_field():
    """One field for text and numbers: the form's widget decides the box type."""
    html = render_field("input", EventForm()["seats"])

    assert 'type="number"' in html


class NoteForm(forms.Form):
    note = forms.CharField(max_length=500, widget=forms.Textarea)


def test_the_textarea_keeps_our_height_and_the_forms_limit():
    html = render_field("textarea", NoteForm()["note"])

    assert 'rows="2"' in html
    assert 'maxlength="500"' in html


def test_the_textarea_takes_rows_from_the_caller():
    assert 'rows="6"' in render_field("textarea", NoteForm()["note"], rows=6)


def test_a_note_starting_with_a_blank_line_keeps_it():
    """Browsers drop the first newline after <textarea>; Django writes one so a real one survives."""
    html = render_field("textarea", NoteForm(data={"note": "\nsecond line"})["note"])

    assert ">\n\nsecond line</textarea>" in html


class BirthdayForm(forms.Form):
    born_at = forms.DateField(initial=datetime.date(1990, 3, 14), widget=forms.DateInput(attrs={"type": "date"}))
    typed = forms.DateField(initial=datetime.date(1990, 3, 14))


@pytest.mark.parametrize("language", ["en", "de", "el"])
def test_a_date_picker_reads_iso_in_every_language(language):
    """Django writes the language's format (German 14.03.1990); a browser date picker reads only ISO."""
    with translation.override(language):
        html = render_field("input", BirthdayForm()["born_at"])

    assert 'type="date"' in html
    assert 'value="1990-03-14"' in html


def test_a_forced_date_type_is_written_in_iso_too():
    with translation.override("de"):
        html = render_field("input", BirthdayForm()["typed"], input_type="date")

    assert 'value="1990-03-14"' in html


@pytest.mark.parametrize("name", ["number", "date", "datetime", "password"])
def test_one_input_field_draws_every_box_type(name):
    """The template names the look; the form's widget decides the type."""
    with pytest.raises(TemplateDoesNotExist):
        render_field(name, EventForm()["title"])


class AlarmForm(forms.Form):
    at = forms.TimeField(initial=datetime.time(7, 30), widget=forms.TimeInput(attrs={"type": "time"}))


def test_a_time_box_gets_a_clock_button_and_an_iso_value():
    with translation.override("de"):
        html = render_field("input", AlarmForm()["at"])

    assert 'type="time"' in html
    assert 'value="07:30"' in html
    assert "fw-md3-trailing-btn" in html
    assert "placeholder" not in html


def test_the_picker_buttons_carry_no_script_of_their_own():
    for html in (render_field("input", BirthdayForm()["born_at"]), render_field("input", AlarmForm()["at"])):
        assert "onclick" not in html
        assert "data-picker-open" in html


class ChoiceWidgetsForm(forms.Form):
    level = forms.ChoiceField(choices=[("a", "A"), ("b", "B")], widget=forms.RadioSelect)
    tags = forms.MultipleChoiceField(choices=[("a", "A")])
    agree = forms.BooleanField()


@pytest.mark.parametrize(
    ("name", "form_field"),
    [
        ("select", "level"),
        ("select", "tags"),
        ("input", "agree"),
        ("textarea", "level"),
        ("checkbox", "level"),
        ("toggle", "level"),
    ],
)
def test_a_frame_refuses_a_widget_it_cannot_wrap(name, form_field):
    """Radio buttons inside a dropdown's outline is a broken field; it fails loudly instead."""
    with pytest.raises(TypeError, match="widget"):
        render_field(name, ChoiceWidgetsForm()[form_field])


def test_the_select_marks_the_chosen_option_by_value():
    html = render_field("select", EventForm(initial={"status": "live"})["status"])

    assert '<option value="live" selected>' in html
    assert '<option value="draft">' in html


class ConsentForm(forms.Form):
    agree = forms.BooleanField(help_text="You can change this later")


@pytest.mark.parametrize(("initial", "ticked"), [(True, True), (False, False)])
def test_the_checkbox_is_ticked_by_its_value(initial, ticked):
    html = render_field("checkbox", ConsentForm(initial={"agree": initial})["agree"])

    assert ("checked" in html) is ticked


def test_a_submitted_false_is_unticked():
    html = render_field("checkbox", ConsentForm(data={"agree": "false"})["agree"])

    assert "checked" not in html


def test_the_checkbox_points_at_its_help_text():
    html = render_field("checkbox", ConsentForm()["agree"])

    assert 'aria-describedby="id_agree_helptext"' in html
    assert 'id="id_agree_helptext"' in html


class PickForm(forms.Form):
    size = forms.ChoiceField(choices=[("s", "Small"), ("l", "Large")], widget=forms.RadioSelect, initial="l")
    days = forms.MultipleChoiceField(choices=[("0", "Monday"), ("1", "Tuesday")], widget=forms.CheckboxSelectMultiple)
    grouped = forms.ChoiceField(
        choices=[("Berlin", [("b1", "Room 1")]), ("Athens", [("a1", "Hall")])], widget=forms.RadioSelect
    )
    plain = forms.ChoiceField(choices=[("x", "X")])


def test_choices_draws_radios_or_checkboxes_as_the_form_says():
    radios = render_field("choices", PickForm()["size"])
    boxes = render_field("choices", PickForm()["days"])

    assert radios.count('type="radio"') == 2
    assert "fw-choice-input--radio" in radios
    assert 'value="l" class="fw-choice-input fw-choice-input--radio" required id="id_size_1" checked' in radios
    assert boxes.count('type="checkbox"') == 2
    assert "fw-choice-input--checkbox" in boxes


def test_choices_draws_grouped_options_under_their_heading():
    html = render_field("choices", PickForm()["grouped"])

    assert html.index("Berlin") < html.index("Room 1") < html.index("Athens") < html.index("Hall")


def test_every_option_gets_the_htmx_settings():
    html = render_field("choices", PickForm()["size"], hx_get="/x/", hx_indicator="#spin")

    assert html.count('hx-get="/x/"') == 2
    assert html.count('hx-indicator="#spin"') == 2


def test_choices_refuses_a_dropdown():
    with pytest.raises(TypeError, match="RadioSelect or CheckboxSelectMultiple"):
        render_field("choices", PickForm()["plain"])


@pytest.mark.parametrize(("initial", "on"), [(True, True), (False, False)])
def test_the_toggle_is_on_by_its_value(initial, on):
    html = render_field("toggle", ConsentForm(initial={"agree": initial})["agree"])

    assert ("checked" in html) is on


def test_the_toggle_points_at_its_help_text():
    html = render_field("toggle", ConsentForm()["agree"])

    assert 'aria-describedby="id_agree_helptext"' in html
    assert 'id="id_agree_helptext"' in html


def test_the_toggle_writes_htmx_only_when_it_makes_a_request():
    quiet = render_field("toggle", ConsentForm()["agree"], hx_swap="none")
    live = render_field("toggle", ConsentForm()["agree"], hx_get="/filters/", hx_swap="none")

    assert "hx-" not in quiet
    assert 'hx-get="/filters/"' in live
    assert 'hx-swap="none"' in live


def test_the_toggle_points_at_its_error():
    html = render_field("toggle", ConsentForm(data={})["agree"])

    assert "id_agree_error" in html.split('aria-describedby="')[1].split('"')[0]
    assert 'id="id_agree_error"' in html
