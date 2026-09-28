import re
from functools import cached_property

from django.forms import BoundField, ModelChoiceField, ModelMultipleChoiceField

FIELD_TEMPLATES = "phoxtail_core/forms/fields"
FIELD_NAME = re.compile(r"[a-z_]+")


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
    return bound_field.render(f"{FIELD_TEMPLATES}/{name}.html", {**options, "field": bound_field})
