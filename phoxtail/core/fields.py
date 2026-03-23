from functools import cached_property

from django.forms import BoundField, ModelChoiceField, ModelMultipleChoiceField


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
