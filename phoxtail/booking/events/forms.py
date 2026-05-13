from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .constants import EventStatus, EventUpdateScope, RecurrenceWeekday
from .models import Event
from .services import EventService


class EventCreateForm(forms.ModelForm):
    """
    Form for creating events in the admin scheduling interface.
    """

    # Explicit field definition for ArrayField with choices
    recurrence_byweekday = forms.MultipleChoiceField(
        choices=RecurrenceWeekday.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Weekdays"),
        help_text=_("Select which days of the week to repeat on"),
    )

    def __init__(self, *args, location=None, **kwargs):
        """
        Initialize the form with optional location filtering for spaces.

        Args:
            location: Location instance to filter spaces by
        """
        super().__init__(*args, **kwargs)

        # Filter spaces by location if provided
        if location:
            from phoxtail.booking.core.models import Space

            self.fields["space"].queryset = Space.objects.filter(location=location, is_active=True).order_by("name")

        # Override Django's default min=0 for PositiveIntegerField
        self.fields["recurrence_interval"].widget.attrs["min"] = 1

    class Meta:
        model = Event
        fields = [
            "service",
            "start_datetime",
            "end_datetime",
            "space",
            "staff",
            "capacity",
            "status",
            "group",
            "notes",
            "recurrence_freq",
            "recurrence_interval",
            "recurrence_byweekday",
            "recurrence_bymonthday",
            "recurrence_bysetpos",
            "recurrence_byweekday_monthly",
            "recurrence_until",
        ]
        widgets = {
            "start_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "recurrence_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "staff": forms.CheckboxSelectMultiple,
            "status": forms.RadioSelect,
        }

    def clean_recurrence_byweekday(self):
        """Convert string values to integers for ArrayField."""
        data = self.cleaned_data.get("recurrence_byweekday")
        if data:
            return [int(day) for day in data]
        return []

    def clean(self):
        """
        Perform cross-field validation using the admin gateway.
        """
        cleaned_data = super().clean()

        if not self.errors:
            result = EventService().admin.validate_create(**cleaned_data)
            if result.has_errors:
                for err in result.errors:
                    self.add_error(err.field, err.message)
            if result.has_warnings:
                self._warnings = result.warnings

        return cleaned_data

    def save(self, commit=True):
        """
        Save the event using the admin gateway for creation logic.
        """
        if not commit:
            return super().save(commit=False)

        return EventService().admin.create(**self.cleaned_data)


class EventUpdateForm(forms.ModelForm):
    """
    Form for updating events in the admin scheduling interface.
    Includes update_scope field for recurring series management.
    Does not include recurrence fields since those are only editable on template events.
    """

    # Update scope field for recurring series (not saved to model)
    update_scope = forms.ChoiceField(
        choices=EventUpdateScope.choices,
        required=False,
        initial=EventUpdateScope.THIS_EVENT_ONLY,
        label=_("Update scope"),
        help_text=_("Choose which events to update in the recurring series"),
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the form and filter spaces based on the event's location.
        """
        super().__init__(*args, **kwargs)

        # Filter spaces by the event's location if instance exists
        if self.instance and self.instance.pk and self.instance.space:
            from phoxtail.booking.core.models import Space

            location = self.instance.space.location
            self.fields["space"].queryset = Space.objects.filter(location=location, is_active=True).order_by("name")

    class Meta:
        model = Event
        fields = [
            "service",
            "start_datetime",
            "end_datetime",
            "space",
            "staff",
            "capacity",
            "status",
            "group",
            "notes",
        ]
        widgets = {
            "start_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "staff": forms.CheckboxSelectMultiple,
            "status": forms.RadioSelect,
        }

    def clean(self):
        """
        Perform cross-field validation using the admin gateway.
        Bulk scope validation is handled inside the gateway.
        """
        cleaned_data = super().clean()

        if not self.errors:
            # Extract update_scope before spreading — it's not a model field
            validate_data = {k: v for k, v in cleaned_data.items() if k != "update_scope"}
            update_scope = cleaned_data.get("update_scope", EventUpdateScope.THIS_EVENT_ONLY)

            result = EventService(self.instance).admin.validate_update(update_scope=update_scope, **validate_data)
            if result.has_errors:
                for err in result.errors:
                    self.add_error(err.field, err.message)
            if result.has_warnings:
                self._warnings = result.warnings

        return cleaned_data

    def save(self, commit=True):
        """
        Save the event using the admin gateway for update logic.
        Respects the update_scope for recurring series updates.
        """
        if not commit:
            return super().save(commit=False)

        # Extract update_scope from cleaned_data (not a model field)
        update_scope = self.cleaned_data.pop("update_scope", EventUpdateScope.THIS_EVENT_ONLY)

        event, events_updated = EventService(self.instance).admin.update(update_scope=update_scope, **self.cleaned_data)

        # Store the count for potential use in the view
        self.events_updated = events_updated

        return event


class TemplateEventUpdateForm(forms.ModelForm):
    """
    Form for updating template events (recurrence templates).

    Template events define the recurrence pattern for a series. This form includes
    all event configuration fields (service, datetime, space, staff, capacity, etc.)
    plus recurrence pattern fields (frequency, interval, weekdays, monthly options, end date).

    Changes to template events affect how future events in the series are generated,
    but do not modify existing generated events.
    """

    # Explicit field definition for ArrayField with choices
    recurrence_byweekday = forms.MultipleChoiceField(
        choices=RecurrenceWeekday.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Weekdays"),
        help_text=_("Select which days of the week to repeat on"),
    )

    def __init__(self, *args, **kwargs):
        """
        Initialize the form and filter spaces based on location.
        """
        super().__init__(*args, **kwargs)

        # Filter spaces by the event's location if instance exists
        if self.instance and self.instance.pk and self.instance.space:
            from phoxtail.booking.core.models import Space

            location = self.instance.space.location
            self.fields["space"].queryset = Space.objects.filter(location=location, is_active=True).order_by("name")

        # Override Django's default min=0 for PositiveIntegerField
        self.fields["recurrence_interval"].widget.attrs["min"] = 1

    class Meta:
        model = Event
        fields = [
            "service",
            "start_datetime",
            "end_datetime",
            "space",
            "staff",
            "capacity",
            "status",
            "group",
            "notes",
            "recurrence_freq",
            "recurrence_interval",
            "recurrence_byweekday",
            "recurrence_bymonthday",
            "recurrence_bysetpos",
            "recurrence_byweekday_monthly",
            "recurrence_until",
        ]
        widgets = {
            "start_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_datetime": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "recurrence_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "staff": forms.CheckboxSelectMultiple,
            "status": forms.RadioSelect,
        }

    def clean_recurrence_byweekday(self):
        """Convert string values to integers for ArrayField."""
        data = self.cleaned_data.get("recurrence_byweekday")
        if data:
            return [int(day) for day in data]
        return []

    def clean(self):
        """
        Perform cross-field validation using the admin gateway.
        """
        cleaned_data = super().clean()

        if not self.errors:
            result = EventService(self.instance).admin.validate_update_template(**cleaned_data)
            if result.has_errors:
                for err in result.errors:
                    self.add_error(err.field, err.message)
            if result.has_warnings:
                self._warnings = result.warnings

        return cleaned_data

    def save(self, commit=True):
        """
        Save the template event using the admin gateway for update logic.
        """
        if not commit:
            return super().save(commit=False)

        return EventService(self.instance).admin.update_template(**self.cleaned_data)


class EventBulkUpdateStatusForm(forms.Form):
    """
    Form for bulk updating event statuses within a date range.
    Used in the admin scheduling interface.
    """

    from_datetime = forms.DateTimeField(
        required=True,
        label=_("From"),
        help_text=_("Start of date range (inclusive)"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    to_datetime = forms.DateTimeField(
        required=True,
        label=_("To"),
        help_text=_("End of date range (inclusive)"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    status = forms.ChoiceField(
        choices=EventStatus.choices,
        required=True,
        label=_("New Status"),
        help_text=_("The status to apply to all events in the date range"),
        widget=forms.RadioSelect,
    )

    def clean(self):
        """
        Validate that from_datetime is before or equal to to_datetime.
        """
        cleaned_data = super().clean()
        from_datetime = cleaned_data.get("from_datetime")
        to_datetime = cleaned_data.get("to_datetime")

        if from_datetime and to_datetime:
            if from_datetime > to_datetime:
                raise ValidationError(_("Start date must be before or equal to end date."))

        return cleaned_data
