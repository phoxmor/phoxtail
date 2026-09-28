import copy
import re
from functools import cached_property

from django.forms import BoundField, ModelChoiceField, ModelMultipleChoiceField
from django.forms.widgets import DateTimeBaseInput
from django.utils.html import escape

FIELD_TEMPLATES = "phoxtail_core/forms/fields"
FIELD_NAME = re.compile(r"[a-z_]+")
HTMX_DEFAULTS = {"hx_swap": "innerHTML", "hx_trigger": "change"}
HTMX_REQUESTS = ("hx_get", "hx_post", "hx_put", "hx_patch", "hx_delete")
# A browser's date, date-time and time pickers read only these formats,
# whatever the language; Django's widgets write the language's own.
PICKER_FORMATS = {"date": "%Y-%m-%d", "datetime-local": "%Y-%m-%dT%H:%M", "time": "%H:%M"}
# The button at the end of the box follows the box's type.
TRAILING = {"date": "calendar", "datetime-local": "calendar", "time": "clock"}


class MultiSelectChipsBoundField(BoundField):
    """BoundField that exposes selected/available items as properties."""

    @cached_property
    def selected_items(self):
        queryset = self.field.queryset
        if queryset is None:
            return []
        value = self.value()
        if not value:
            return queryset.none()
        if isinstance(value, (list, tuple)):
            pks = [str(pk) for pk in value if pk]
        else:
            pks = [str(value)] if value else []
        if not pks:
            return queryset.none()
        return queryset.model.objects.filter(pk__in=pks)

    @cached_property
    def available_items(self):
        queryset = self.field.queryset
        if queryset is None:
            return []
        value = self.value()
        if isinstance(value, (list, tuple)):
            selected_pks = [str(pk) for pk in value if pk]
        else:
            selected_pks = [str(value)] if value else []
        if selected_pks:
            return queryset.exclude(pk__in=selected_pks)
        return queryset


class MultiSelectChipsField(ModelMultipleChoiceField):
    """ModelMultipleChoiceField with selected/available items."""

    def get_bound_field(self, form, field_name):
        return MultiSelectChipsBoundField(form, self, field_name)


class SingleSelectSearchBoundField(BoundField):
    """BoundField that exposes selected_item and available_items for single-select."""

    @cached_property
    def selected_item(self):
        queryset = self.field.queryset
        if queryset is None:
            return None
        value = self.value()
        if not value:
            return None
        pk = str(value)
        try:
            return queryset.model.objects.get(pk=pk)
        except queryset.model.DoesNotExist:
            return None

    @cached_property
    def available_items(self):
        queryset = self.field.queryset
        if queryset is None:
            return []
        value = self.value()
        if value:
            return queryset.exclude(pk=str(value))
        return queryset


class SingleSelectSearchField(ModelChoiceField):
    """ModelChoiceField with selected_item/available_items."""

    def get_bound_field(self, form, field_name):
        return SingleSelectSearchBoundField(form, self, field_name)


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
    values = {
        **options,
        "field": bound_field,
        "supporting": supporting(bound_field, options),
        "htmx": {key: value for key, value in options.items() if key.startswith("hx_")},
        "trailing": TRAILING.get(control_type(bound_field, options.get("input_type")), ""),
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


def render_control(bound_field, /, *, input_type=None, htmx=None, **options):
    """Draw a field's control with Django's own widget, plus phoxtail's attributes.

    The widget brings what the form declares (value formatted for the active
    language, ``required``, ``disabled``, ``maxlength``, ``autocomplete``,
    ``aria-describedby``...); ``options`` add HTML attributes on top:
    ``class="x"``, ``autofocus=True``, and any ``hx_*`` setting, written only
    when the control makes a request (``hx_get``, ``hx_post``, ``hx_put``,
    ``hx_patch`` or ``hx_delete``). ``htmx`` takes a field's ``hx_*`` options at
    once, as ``render_field`` gathers them.
    """
    widget = copy.copy(bound_field.field.widget)
    if input_type:
        widget.input_type = input_type
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
    return bound_field.as_widget(widget=widget, attrs=attrs)


def _given(value):
    """An option counts unless it is missing, False or empty; 0 counts."""
    return value is not None and value is not False and value != ""
