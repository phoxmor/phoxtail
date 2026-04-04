import django_filters
from django import forms

from phoxtail.booking.core.models import Location, Space, Staff
from phoxtail.booking.events.models import Event
from phoxtail.booking.services.models import Service


class EventFilter(django_filters.FilterSet):
    """Filter for Event queryset with location and time filtering."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "filter")
        super().__init__(*args, **kwargs)

    location = django_filters.ModelChoiceFilter(
        field_name="space__location",
        queryset=Location.objects.filter(is_active=True).order_by("name"),
    )

    space = django_filters.ModelChoiceFilter(
        field_name="space",
        queryset=Space.objects.filter(is_active=True).order_by("name"),
    )

    service = django_filters.ModelChoiceFilter(
        field_name="service",
        queryset=Service.objects.filter(is_active=True).order_by("name"),
    )

    date = django_filters.DateFilter(
        field_name="start_datetime__date",
        label="Select date",
    )

    staff = django_filters.ModelChoiceFilter(
        field_name="staff",
        queryset=Staff.objects.all().order_by("user__first_name", "user__last_name"),
    )

    class Meta:
        model = Event
        fields = ["location", "space", "service", "date", "staff"]


class ScheduleFilter(django_filters.FilterSet):
    """Filter for Event queryset with schedule-specific options."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "filter")
        super().__init__(*args, **kwargs)

    location = django_filters.ModelChoiceFilter(
        field_name="space__location",
        queryset=Location.objects.filter(is_active=True).order_by("name"),
    )

    space = django_filters.ModelChoiceFilter(
        field_name="space",
        queryset=Space.objects.filter(is_active=True).order_by("name"),
    )

    service = django_filters.ModelChoiceFilter(
        field_name="service",
        queryset=Service.objects.filter(is_active=True).order_by("name"),
    )

    date = django_filters.DateFilter(
        field_name="start_datetime__date",
        label="Select date",
        method="filter_date",
    )

    staff = django_filters.ModelChoiceFilter(
        field_name="staff",
        queryset=Staff.objects.all().order_by("user__first_name", "user__last_name"),
    )

    show_empty_rows = django_filters.BooleanFilter(
        method="filter_show_empty_rows",
        label="Show empty rows",
        widget=forms.CheckboxInput(attrs={"value": "true"}),
    )

    def filter_date(self, queryset, name, value):
        """Date filter doesn't affect queryset in schedule view - used for navigation only."""
        return queryset

    def filter_show_empty_rows(self, queryset, name, value):
        """This filter doesn't affect the queryset - it's used for UI state only."""
        return queryset

    class Meta:
        model = Event
        fields = ["location", "space", "service", "date", "staff", "show_empty_rows"]
