import copy
import re
from functools import cached_property

from django.core.exceptions import ValidationError
from django.forms import BoundField, ModelChoiceField
from django.forms.widgets import (
    CheckboxInput,
    CheckboxSelectMultiple,
    DateTimeBaseInput,
    HiddenInput,
    Input,
    NullBooleanSelect,
    RadioSelect,
    Select,
    SelectMultiple,
    Textarea,
)
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from phonenumber_field.widgets import PhoneNumberPrefixWidget

FIELD_TEMPLATES = "phoxtail_core/forms/fields"
FIELD_NAME = re.compile(r"[a-z_]+")
HTMX_DEFAULTS = {"hx_swap": "innerHTML", "hx_trigger": "change"}
HTMX_REQUESTS = ("hx_get", "hx_post", "hx_put", "hx_patch", "hx_delete")
# A browser's date, date-time and time pickers read only these formats,
# whatever the language; Django's widgets write the language's own.
PICKER_FORMATS = {"date": "%Y-%m-%d", "datetime-local": "%Y-%m-%dT%H:%M", "time": "%H:%M"}
# The widget each frame is built around. Django draws the control, so a
# frame given another widget would wrap the wrong element (radio buttons in
# a dropdown's outline); render_field refuses the pair instead.
FRAME_WIDGETS = {
    "input": (Input, (CheckboxInput, HiddenInput)),
    "textarea": (Textarea, ()),
    "select": (Select, (SelectMultiple,)),
    "checkbox": (CheckboxInput, ()),
    "toggle": (CheckboxInput, ()),
    "choices": ((RadioSelect, CheckboxSelectMultiple), ()),
    "segmented_control": (RadioSelect, (CheckboxSelectMultiple,)),
    "phone": (PhoneNumberPrefixWidget, ()),
    "single_select_search": (HiddenInput, ()),
}
# The options each field reads, and whether it passes any hx_* option on to
# its control. render_field refuses others, so a misspelled option fails
# instead of being ignored; a test keeps each list equal to its template.
SHARED_OPTIONS = {"label", "show_label", "required", "show_required", "help_text", "show_help_text"}
FIELD_OPTIONS = {
    "input": (SHARED_OPTIONS | {"autofocus", "input_type", "placeholder"}, True),
    "textarea": (SHARED_OPTIONS | {"rows"}, True),
    "select": (SHARED_OPTIONS, True),
    "checkbox": (SHARED_OPTIONS - {"show_label"}, True),
    "toggle": ({"label", "help_text", "show_help_text"}, True),
    "choices": (SHARED_OPTIONS | {"grid_modifier"}, True),
    "segmented_control": (SHARED_OPTIONS | {"variant", "size"}, True),
    "phone": (SHARED_OPTIONS | {"prefix_label"}, True),
    "single_select_search": (
        SHARED_OPTIONS
        | {"search_url", "hx_include", "item_template", "is_active", "search_placeholder", "trigger_placeholder"},
        False,
    ),
}
# The button at the end of the box follows the box's type.
TRAILING = {"date": "calendar", "datetime-local": "calendar", "time": "clock", "password": "eye"}


class SingleSelectSearchBoundField(BoundField):
    """BoundField that exposes selected_item and available_items for single-select."""

    @cached_property
    def selected_item(self):
        """The chosen item, if it is one of the field's choices.

        The field's own check (``to_python``) looks it up in the field's
        queryset and refuses a value that is not a choice or not a key at all.
        """
        if self.field.queryset is None:
            return None
        try:
            return self.field.to_python(self.value())
        except ValidationError:
            return None

    @cached_property
    def available_items(self):
        queryset = self.field.queryset
        if queryset is None:
            return []
        if self.selected_item:
            return queryset.exclude(pk=self.selected_item.pk)
        return queryset


class SingleSelectSearchField(ModelChoiceField):
    """ModelChoiceField with selected_item/available_items.

    The pick travels in a hidden box; the search panel around it is drawn by
    the field template.
    """

    widget = HiddenInput

    def get_bound_field(self, form, field_name):
        return SingleSelectSearchBoundField(form, self, field_name)


class BooleanFilterSelect(NullBooleanSelect):
    """A yes/no filter's dropdown: All, Yes, No.

    Django's NullBooleanSelect, whose empty choice reads "All" rather than
    "Unknown": in a filter, no answer means no filtering.
    """

    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.choices = [("unknown", _("All")), ("true", _("Yes")), ("false", _("No"))]


def render_field(name, bound_field, /, **options):
    """Draw a bound form field with one of core's field templates.

    Django's own ``BoundField.render`` draws it, through the form's renderer, so
    the template sees the field and the options passed here, nothing else.
    """
    if not isinstance(name, str) or not FIELD_NAME.fullmatch(name):
        raise ValueError(
            f"{name!r} is not a field name: use a template name from "
            f"{FIELD_TEMPLATES}/, without folders (a field's parts are not "
            "drawn on their own)"
        )
    if not isinstance(bound_field, BoundField):
        raise TypeError(
            f"the {name!r} field needs a form field, got {bound_field!r}; "
            "check the spelling of the form and field names"
        )
    if name in FRAME_WIDGETS:
        widget = bound_field.field.widget
        accepted, refused = FRAME_WIDGETS[name]
        if not isinstance(widget, accepted) or isinstance(widget, refused):
            kinds = " or ".join(kind.__name__ for kind in (accepted if isinstance(accepted, tuple) else (accepted,)))
            raise TypeError(
                f"the {name!r} field draws a {kinds} widget, but "
                f"{bound_field.name!r} uses {type(widget).__name__}; draw it with "
                "the field that matches its widget, or change the widget in the form"
            )
    if name in FIELD_OPTIONS:
        known, htmx = FIELD_OPTIONS[name]
        unknown = sorted(key for key in options if key not in known and not (htmx and key.startswith("hx_")))
        if unknown:
            valid = ", ".join(sorted(known) + (["hx_*"] if htmx else []))
            raise TypeError(f"the {name!r} field has no option {', '.join(unknown)}; its options are {valid}")
    values = {
        **options,
        "field": bound_field,
        "supporting": supporting(bound_field, options),
        "htmx": {key: value for key, value in options.items() if key.startswith("hx_")},
        "trailing": TRAILING.get(control_type(bound_field, options.get("input_type")), ""),
        "control_type": control_type(bound_field, options.get("input_type")),
    }
    return bound_field.render(f"{FIELD_TEMPLATES}/{name}.html", values)


def control_type(bound_field, input_type=None):
    """The type of the box a field draws: the caller's override, else the form's widget."""
    return input_type or getattr(bound_field.field.widget, "input_type", "")


def supporting(bound_field, options):
    """What the line under a field shows: its errors, else its help text, else nothing."""
    if bound_field.errors:
        return "errors"
    if options.get("show_help_text") is not False and (options.get("help_text") or bound_field.help_text):
        return "help"
    return ""


def render_control(bound_field, /, *, input_type=None, htmx=None, part=None, **options):
    """Draw a field's control with Django's own widget, plus phoxtail's attributes.

    The widget brings what the form declares (value formatted for the active
    language, ``required``, ``disabled``, ``maxlength``, ``autocomplete``,
    ``aria-describedby``...); ``options`` add HTML attributes on top:
    ``class="x"``, ``autofocus=True``, and any ``hx_*`` setting, written only
    when the control makes a request (``hx_get``, ``hx_post``, ``hx_put``,
    ``hx_patch`` or ``hx_delete``). ``htmx`` takes a field's ``hx_*`` options at
    once, as ``render_field`` gathers them. ``part`` draws one control of a
    multi-part widget (a phone number's country and number), so each can sit
    in its own outline; it keeps the name and value the field reads back.
    """
    widget = copy.copy(bound_field.field.widget)
    if input_type:
        widget.input_type = input_type
    # Django's documented hooks for how a widget draws itself and its options.
    for hook in ("template_name", "option_template_name"):
        if options.get(hook):
            setattr(widget, hook, options.pop(hook))
        options.pop(hook, None)
    picker = control_type(bound_field, input_type) in PICKER_FORMATS
    if picker and isinstance(widget, DateTimeBaseInput):
        widget.format = PICKER_FORMATS[widget.input_type]
    if picker:
        # A picker shows its own scaffold; HTML gives it no placeholder.
        options.pop("placeholder", None)
    htmx = {**(htmx or {}), **{key: options.pop(key) for key in list(options) if key.startswith("hx_")}}
    attrs = {key.replace("_", "-"): value for key, value in options.items() if _given(value)}
    if any(_given(htmx.get(key)) for key in HTMX_REQUESTS):
        for key, value in {**HTMX_DEFAULTS, **{k: v for k, v in htmx.items() if _given(v)}}.items():
            attrs[key.replace("_", "-")] = value
    # A string written in a template is marked safe, so Django would print its
    # quotes raw and break the attribute; each value is escaped here, once.
    attrs = {key: escape(value) if isinstance(value, str) else value for key, value in attrs.items()}
    if part is None:
        return bound_field.as_widget(widget=widget, attrs=attrs)
    return _render_part(bound_field, widget, attrs, part)


def _render_part(bound_field, widget, attrs, part):
    """One control of a MultiWidget, drawn as BoundField.as_widget draws a whole one.

    Django draws a MultiWidget's controls together, through one template; this
    takes the context Django builds for them and draws only the one asked for.
    """
    attrs = bound_field.build_widget_attrs(attrs, widget)
    if bound_field.auto_id and "id" not in widget.attrs:
        attrs.setdefault("id", bound_field.auto_id)
    context = widget.get_context(bound_field.html_name, bound_field.value(), attrs)
    control = context["widget"]["subwidgets"][part]
    return mark_safe(bound_field.form.renderer.render(control["template_name"], {"widget": control}))


def _given(value):
    """An option counts unless it is missing, False or empty; 0 counts."""
    return value is not None and value is not False and value != ""
