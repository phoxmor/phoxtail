from collections import defaultdict
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, Count, Value, When
from django.db.models.fields import BooleanField
from django.http import HttpRequest
from django.utils import timezone

from phoxtail.booking.core.models import Location, Space
from phoxtail.booking.events.filters import EventFilter, ScheduleFilter
from phoxtail.booking.events.models import Event


# Booking
class BookingContextBuilder:
    """Builds booking context for filters and daily calendar views."""

    def __init__(self, request: HttpRequest):
        self.request = request
        self.query_params = None
        self.locations = None
        self.location = None
        self.location_count = None
        self.space_queryset = None
        self.filterset = None
        self.filter_count = None

    def _extract_query_params(self):
        """Extract query parameters from GET or POST request."""
        self.query_params = self.request.GET.copy() if self.request.method == "GET" else self.request.POST.copy()

    def _load_locations(self):
        """Load active locations and count."""
        location_filter = EventFilter.get_filters()["location"]
        self.locations = location_filter.queryset
        self.location_count = self.locations.count()

    def _resolve_location(self):
        """Resolve location from params or auto-select if only one exists."""
        if self.location_count == 1:
            self.query_params["filter-location"] = str(self.locations.first().id)

    def _build_space_queryset(self):
        """Build space queryset filtered by selected location."""
        if self.query_params.get("filter-location"):
            self.space_queryset = Space.objects.filter(
                location_id=self.query_params.get("filter-location"), is_active=True
            ).order_by("name")
        else:
            self.space_queryset = Space.objects.filter(is_active=True).order_by("name")

    def _create_filterset(self, base_queryset):
        """Create and configure filterset with space queryset."""
        self.filterset = EventFilter(self.query_params, queryset=base_queryset)
        self.filterset.filters["space"].queryset = self.space_queryset

    def _calculate_filter_count(self):
        """Calculate number of active filters."""
        prefix = self.filterset.form.prefix
        filter_keys = [f"{prefix}-{key}" for key in self.filterset.filters if key != "date"]
        self.filter_count = sum(
            1
            for k, v in self.filterset.data.items()
            if k in filter_keys and v and (k != "filter-location" or self.location_count > 1)
        )

    def _prepare_base_context(self, base_queryset):
        """Prepare common context for both lightweight and heavy builders."""
        self._extract_query_params()
        self._load_locations()
        self._resolve_location()
        self._build_space_queryset()
        self._create_filterset(base_queryset)
        self._calculate_filter_count()

    def build_filters_context(self):
        """Build lightweight context for filter form only."""
        self._prepare_base_context(base_queryset=Event.objects.none())
        return {
            "filterset": self.filterset,
            "location_count": self.location_count,
            "filter_count": self.filter_count,
        }

    def _parse_target_date(self):
        """Parse target date from query params or use today."""
        try:
            location_id = self.query_params.get("filter-location")
            if location_id:
                self.location = self.locations.get(id=location_id)
                today = timezone.now().astimezone(self.location.timezone).date()
            else:
                today = timezone.now().date()
        except (models.ObjectDoesNotExist, ValidationError):
            today = timezone.now().date()

        date_str = self.query_params.get("filter-date")
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = today

        self.query_params["filter-date"] = target_date.strftime("%Y-%m-%d")
        return target_date, today

    def _calculate_day_navigation(self, target_date, today):
        """Calculate day offset and navigation dates."""
        day_offset = (target_date - today).days
        previous_date = target_date - timedelta(days=1)
        next_date = target_date + timedelta(days=1)

        return {
            "target_date": target_date,
            "today": today,
            "day_offset": day_offset,
            "is_today": target_date == today,
            "day_display": target_date.strftime("%A, %B %d, %Y"),
            "previous_date": previous_date.strftime("%Y-%m-%d"),
            "next_date": next_date.strftime("%Y-%m-%d"),
            "today_date": today.strftime("%Y-%m-%d"),
        }

    def _build_event_queryset(self, target_date):
        """Build event queryset with annotations for the target date."""
        return (
            Event.objects.order_by("start_datetime")
            .filter(start_datetime__date=target_date, is_recurrence_template=False)
            .select_related("service", "space", "space__location", "group")
            .prefetch_related("staff", "reservations")
            .annotate(
                reservation_count=Count("reservations"),
                is_past=Case(
                    When(start_datetime__lt=timezone.now(), then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
        )

    def build_full_context(self):
        """Build complete booking context with events for the day."""
        # Step 1: Prepare lightweight context
        self._prepare_base_context(base_queryset=Event.objects.none())

        # Step 2: Parse and calculate date navigation
        target_date, today = self._parse_target_date()
        nav_context = self._calculate_day_navigation(target_date, today)

        # Step 3: NOW do the expensive event query
        event_queryset = self._build_event_queryset(target_date)

        # Step 4: Recreate filterset with REAL queryset
        self._create_filterset(event_queryset)
        events = self.filterset.qs

        # Step 5: Recalculate filter count with final filterset
        self._calculate_filter_count()

        return {
            "events": events,
            "filterset": self.filterset,
            "location": self.location,
            "location_count": self.location_count,
            "filter_count": self.filter_count,
            **nav_context,
        }

    @classmethod
    def get_filters_context(cls, request: HttpRequest):
        """Public API: Get lightweight filter context."""
        return cls(request).build_filters_context()

    @classmethod
    def get_full_context(cls, request: HttpRequest):
        """Public API: Get complete booking context."""
        return cls(request).build_full_context()


# Scheduling
class ScheduleContextBuilder:
    """Builds schedule context for filters and full schedule views."""

    def __init__(self, request: HttpRequest):
        self.request = request
        self.query_params = None
        self.locations = None
        self.location = None
        self.location_count = None
        self.space_queryset = None
        self.filterset = None
        self.filter_count = None

    def _extract_query_params(self):
        """Extract query parameters from GET or POST request."""
        self.query_params = self.request.GET.copy() if self.request.method == "GET" else self.request.POST.copy()

    def _load_locations(self):
        """Load active locations and count."""
        self.locations = Location.objects.filter(is_active=True)
        self.location_count = self.locations.count()

    def _resolve_location(self, base_queryset):
        """Resolve location from params or auto-select if only one exists."""
        temp_filterset = ScheduleFilter(self.query_params, queryset=base_queryset)
        temp_filterset.form.is_valid()
        self.location = temp_filterset.form.cleaned_data.get("location")

        if not self.location and self.location_count == 1:
            self.query_params["filter-location"] = str(self.locations.first().id)
            temp_filterset = ScheduleFilter(self.query_params, queryset=base_queryset)
            temp_filterset.form.is_valid()
            self.location = temp_filterset.form.cleaned_data.get("location")

        return temp_filterset

    def _build_space_queryset(self):
        """Build space queryset filtered by selected location."""
        if self.location:
            self.space_queryset = Space.objects.filter(location=self.location, is_active=True).order_by("name")
        else:
            self.space_queryset = Space.objects.filter(is_active=True).order_by("name")

    def _create_filterset(self, base_queryset):
        """Create and validate filterset with space queryset assigned."""
        self.filterset = ScheduleFilter(self.query_params, queryset=base_queryset)
        self.filterset.form.is_valid()
        self.filterset.filters["space"].queryset = self.space_queryset
        self.filterset.form.fields["space"].queryset = self.space_queryset

    def _calculate_filter_count(self):
        """Calculate number of active filters."""
        prefix = self.filterset.form.prefix
        filter_keys = [f"{prefix}-{key}" for key in self.filterset.filters if key not in ["date", "show_empty_rows"]]
        self.filter_count = sum(
            1
            for k, v in self.filterset.data.items()
            if k in filter_keys and v and (k != "filter-location" or self.location_count > 1)
        )

    def _prepare_base_context(self, base_queryset):
        """Prepare common context for both lightweight and heavy builders."""
        self._extract_query_params()
        self._load_locations()
        self._resolve_location(base_queryset)
        self._build_space_queryset()
        self._create_filterset(base_queryset)
        self._calculate_filter_count()

    def build_filters_context(self):
        """Build lightweight context for filter form only."""
        self._prepare_base_context(base_queryset=Event.objects.none())
        return {
            "filterset": self.filterset,
            "filter_count": self.filter_count,
        }

    def _extract_schedule_settings(self):
        """Extract date and show_empty_rows from validated form."""
        target_date = self.filterset.form.cleaned_data.get("date")
        show_empty_rows = self.filterset.form.cleaned_data.get("show_empty_rows", False)
        return target_date, show_empty_rows

    def _calculate_week_navigation(self, target_date):
        """Calculate week boundaries and navigation dates."""
        today = timezone.now().astimezone(self.location.timezone).date() if self.location else timezone.now().date()

        if not target_date:
            target_date = today

        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        week_days = [week_start + timedelta(days=i) for i in range(7)]
        previous_week = week_start - timedelta(days=7)
        next_week = week_start + timedelta(days=7)
        is_current_week = week_start <= today <= week_end

        return {
            "today": today,
            "target_date": target_date,
            "week_start": week_start,
            "week_end": week_end,
            "week_days": week_days,
            "previous_week": previous_week,
            "next_week": next_week,
            "is_current_week": is_current_week,
        }

    def _build_event_queryset(self, week_start, week_end):
        """Build event queryset with annotations for the week."""
        return (
            Event.objects.order_by("start_datetime", "space__name")
            .filter(start_datetime__date__gte=week_start, start_datetime__date__lte=week_end)
            .select_related("service", "space", "space__location")
            .annotate(
                is_past=Case(
                    When(start_datetime__lt=timezone.now(), then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
        )

    def _build_calendar_structure(self, filtered_queryset, week_start, week_end, week_days, today, show_empty_rows):
        """Build week grid with events organized by day and hour."""
        from phoxtail.booking.events.services import EventService

        # Get events with projections (combines real + virtual recurring events)
        # The method auto-detects active recurrence templates internally
        all_events = EventService.get_events_with_recurrence_projections(
            queryset=filtered_queryset,
            start_date=week_start,
            end_date=week_end,
        )

        # Group events by day (convert to event's location timezone first)
        events_by_day = defaultdict(list)
        for event in all_events:
            # Convert event start time to its location's timezone before getting date
            event_location = event.space.location
            event_date = event.start_datetime.astimezone(event_location.timezone).date()
            events_by_day[event_date].append(event)

        # Determine time range for the schedule (6 AM to 10 PM default, or based on events)
        earliest_hour = 0
        latest_hour = 23

        if all_events:
            # Find actual earliest and latest hours from events
            for event in all_events:
                event_location = event.space.location
                event_start_local = event.start_datetime.astimezone(event_location.timezone)
                event_end_local = event.end_datetime.astimezone(event_location.timezone)

                earliest_hour = min(earliest_hour, event_start_local.hour)
                # Add 1 to latest_hour to include the hour where event ends
                latest_hour = max(
                    latest_hour,
                    event_end_local.hour + (1 if event_end_local.minute > 0 else 0),
                )

        # Organize events by day and hour slot
        events_by_day_and_hour = defaultdict(lambda: defaultdict(list))

        for event in all_events:
            event_location = event.space.location
            event_start_local = event.start_datetime.astimezone(event_location.timezone)
            event_date = event_start_local.date()
            start_hour = event_start_local.hour

            # Store event data
            event_data = {
                "event": event,
                "start_hour": start_hour,
            }

            # Add event to the hour slot where it starts
            events_by_day_and_hour[event_date][start_hour].append(event_data)

        # Determine which hours have events (across all days)
        hours_with_events = set()
        for day_events in events_by_day_and_hour.values():
            hours_with_events.update(day_events.keys())

        # Create time slots (hours) - filter based on show_empty_rows setting
        time_slots = []
        for hour in range(earliest_hour, latest_hour + 1):
            # Include this hour if: show_empty_rows is True OR this hour has events
            if show_empty_rows or hour in hours_with_events:
                time_slots.append(
                    {
                        "hour": hour,
                        "display": f"{hour:02d}:00",
                        "display_12h": f"{hour if hour <= 12 else hour - 12}:00 {('AM' if hour < 12 else 'PM')}",
                    }
                )

        # Create week structure with day info
        week_structure = []
        for day in week_days:
            # Create hour slots for this day
            day_hours = []
            for time_slot in time_slots:
                hour = time_slot["hour"]
                day_hours.append(
                    {
                        "hour": hour,
                        "display": time_slot["display"],
                        "display_12h": time_slot["display_12h"],
                        "events": events_by_day_and_hour[day].get(hour, []),
                    }
                )

            week_structure.append(
                {
                    "date": day,
                    "weekday": day.strftime("%A"),
                    "day_display": day.strftime("%b %d"),
                    "is_today": day == today,
                    "events": events_by_day.get(day, []),
                    "hours": day_hours,
                }
            )

        return {
            "week_structure": week_structure,
            "time_slots": time_slots,
        }

    def build_full_context(self):
        """Build complete schedule context with expensive queries and calendar structure."""
        # Step 1: Prepare lightweight context to extract settings
        self._prepare_base_context(base_queryset=Event.objects.none())

        # Step 2: Extract schedule-specific settings
        target_date, show_empty_rows = self._extract_schedule_settings()

        # Step 3: Calculate week navigation
        nav_context = self._calculate_week_navigation(target_date)

        # Step 4: NOW do the expensive event query
        event_queryset = self._build_event_queryset(nav_context["week_start"], nav_context["week_end"])

        # Step 5: Recreate filterset with REAL queryset
        self._create_filterset(event_queryset)
        filtered_events = self.filterset.qs

        # Step 6: Recalculate filter count with final filterset
        self._calculate_filter_count()

        # Step 7: Build expensive schedule structure
        schedule_structure = self._build_calendar_structure(
            filtered_events,
            nav_context["week_start"],
            nav_context["week_end"],
            nav_context["week_days"],
            nav_context["today"],
            show_empty_rows,
        )

        return {
            **schedule_structure,
            "week_display": (
                f"{nav_context['week_start'].strftime('%b %d')} - {nav_context['week_end'].strftime('%b %d, %Y')}"
            ),
            "is_current_week": nav_context["is_current_week"],
            "filterset": self.filterset,
            "previous_week": nav_context["previous_week"].strftime("%Y-%m-%d"),
            "next_week": nav_context["next_week"].strftime("%Y-%m-%d"),
            "today_date": nav_context["today"].strftime("%Y-%m-%d"),
            "location_count": self.location_count,
            "filter_count": self.filter_count,
        }

    @classmethod
    def get_filters_context(cls, request: HttpRequest):
        """Public API: Get lightweight filter context."""
        return cls(request).build_filters_context()

    @classmethod
    def get_full_context(cls, request: HttpRequest):
        """Public API: Get complete schedule context."""
        return cls(request).build_full_context()
