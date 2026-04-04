from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, CharField, OuterRef, Subquery, Value, When
from django.db.models.fields import BooleanField
from django.http import HttpRequest
from django.utils import timezone

from phoxtail.booking.core.models import Space
from phoxtail.booking.events.filters import EventFilter
from phoxtail.booking.events.models import Event
from phoxtail.booking.reservations.models import Reservation


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
        self.query_params = (
            self.request.GET.copy()
            if self.request.method == "GET"
            else self.request.POST.copy()
        )

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
        filter_keys = [
            f"{prefix}-{key}" for key in self.filterset.filters if key != "date"
        ]
        self.filter_count = sum(
            1
            for k, v in self.filterset.data.items()
            if k in filter_keys
            and v
            and (k != "filter-location" or self.location_count > 1)
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
        previous_date = target_date - timedelta(days=1)
        next_date = target_date + timedelta(days=1)

        return {
            "is_today": target_date == today,
            "day_display": target_date.strftime("%A, %B %d, %Y"),
            "previous_date": previous_date.strftime("%Y-%m-%d"),
            "next_date": next_date.strftime("%Y-%m-%d"),
            "today_date": today.strftime("%Y-%m-%d"),
        }

    def _build_event_queryset(self, target_date):
        """Build event queryset with annotations for the target date."""
        from phoxtail.booking.events.constants import EventStatus
        from phoxtail.booking.reservations.constants import ReservationStatus

        user_reservation_qs = Reservation.objects.filter(
            event=OuterRef("pk"), user=self.request.user
        )
        return (
            Event.objects.order_by("start_datetime")
            .filter(start_datetime__date=target_date, is_recurrence_template=False)
            .select_related("service", "space", "space__location")
            .prefetch_related("staff")
            .annotate(
                user_reservation_id=Subquery(user_reservation_qs.values("uuid")[:1]),
                user_reservation_status=Subquery(
                    user_reservation_qs.values("status")[:1]
                ),
                is_past=Case(
                    When(start_datetime__lt=timezone.now(), then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
            .annotate(
                user_reservation_status_display=Case(
                    *[
                        When(
                            user_reservation_status=choice.value,
                            then=Value(choice.label),
                        )
                        for choice in ReservationStatus
                    ],
                    default=Value(""),
                    output_field=CharField(),
                )
            )
            .exclude(status=EventStatus.UNPUBLISHED, user_reservation_id__isnull=True)
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

        # Step 5: Recalculate filter count with final filterset
        self._calculate_filter_count()

        return {
            "filterset": self.filterset,
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
