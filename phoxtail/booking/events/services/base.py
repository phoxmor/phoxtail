"""
Core EventService — queries, projections, recurrence generation, and staff validation.
"""

from functools import cached_property
from typing import TYPE_CHECKING, Optional

from dateutil import rrule
from django.db import transaction
from django.db.models import Value
from django.utils import timezone

from .projected import ProjectedEvent
from .validation import ValidationResult

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from ..models import Event


class EventService:
    """
    Core service class for event-related business logic including capacity,
    reservations, recurrence, and conflict checks.

    Usage:
        # For creation (no existing event):
        event = EventService().admin.create(**data)

        # For operations on existing events:
        EventService(event).admin.update(**data)
    """

    def __init__(self, event: Optional["Event"] = None) -> None:
        self.event = event

    # ------------------------------------------------------------------
    # Domain-specific gateways
    # ------------------------------------------------------------------

    @cached_property
    def admin(self):
        """Access admin domain operations."""
        from .admin import EventServiceAdminGateway

        return EventServiceAdminGateway(self)

    # ------------------------------------------------------------------
    # Reservation / capacity queries
    # ------------------------------------------------------------------

    def get_reservation_count(self) -> int:
        """Count of confirmed and completed reservations for this event."""
        from phoxtail.booking.reservations.constants import ReservationStatus

        return self.event.reservations.filter(
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED]
        ).count()

    def get_reserved_spots_count(self) -> int:
        """Count of reserved spots (confirmed + completed reservations)."""
        return self.get_reservation_count()

    def get_available_spots_count(self) -> int:
        """Number of available spots remaining."""
        return max(0, self.event.capacity - self.get_reservation_count())

    def get_is_full(self) -> bool:
        """Check if the event is at capacity."""
        return self.get_reservation_count() >= self.event.capacity

    def get_short_series_id(self):
        """Get short version of series identifier (first 8 chars of template UUID)."""
        if self.event.is_recurrence_template:
            return str(self.event.uuid)[:8].upper() if self.event.uuid else None
        elif self.event.recurrence_template:
            return str(self.event.recurrence_template.uuid)[:8].upper()
        return None

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_cancelled(self) -> bool:
        """Check if the event is cancelled."""
        from ..constants import EventStatus

        return self.event.status == EventStatus.CANCELLED

    def is_unpublished(self) -> bool:
        """Check if the event is unpublished."""
        from ..constants import EventStatus

        return self.event.status == EventStatus.UNPUBLISHED

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    def user_can_access_event(self, user: "AbstractUser") -> bool:
        """Check if a user has access to book this event based on group membership."""
        if not self.event.group:
            return True
        return self.event.group.has_member(user)

    # ------------------------------------------------------------------
    # Recurrence helpers
    # ------------------------------------------------------------------

    def get_or_create_recurrence_template(self) -> "Event":
        """
        Get or create a template event for this recurring series.

        If this event is already a template, returns itself.
        If this event has a template, returns that template.
        If this event has no template, creates one based on this event's properties.
        """
        if self.event.is_recurrence_template:
            return self.event

        if self.event.recurrence_template:
            return self.event.recurrence_template

        from ..models import Event

        with transaction.atomic():
            template = Event.objects.create(
                service=self.event.service,
                start_datetime=self.event.start_datetime,
                end_datetime=self.event.end_datetime,
                space=self.event.space,
                capacity=self.event.capacity,
                group=self.event.group,
                status=self.event.status,
                notes=self.event.notes,
                recurrence_freq=self.event.recurrence_freq,
                recurrence_interval=self.event.recurrence_interval,
                recurrence_byweekday=self.event.recurrence_byweekday,
                recurrence_bymonthday=self.event.recurrence_bymonthday,
                recurrence_bysetpos=self.event.recurrence_bysetpos,
                recurrence_byweekday_monthly=self.event.recurrence_byweekday_monthly,
                recurrence_until=self.event.recurrence_until,
                is_recurrence_template=True,
                recurrence_template=None,
            )
            template.staff.set(self.event.staff.all())

            self.event.recurrence_template = template
            self.event.save(update_fields=["recurrence_template"])

        return template

    def generate_recurring_events(self, days_ahead=7) -> int:
        """
        Generate recurring event instances based on this event's recurrence settings.

        Conflict-aware: if a real event (from any source) already occupies a
        space-time slot, the recurrence skips that occurrence.

        Returns:
            Number of events created
        """
        if not self.event.recurrence_freq:
            return 0

        template = self.get_or_create_recurrence_template()
        occurrences = EventService(template)._calculate_occurrences(days_ahead)
        duration = template.end_datetime - template.start_datetime

        from ..models import Event

        excluded_dates = set(template.recurrence_excluded_dates or [])

        # Load location-level exclusion periods for this template's location
        from ..models import EventGenerationScheduleExclusionPeriod

        location_exclusion_periods = list(
            EventGenerationScheduleExclusionPeriod.objects.filter(
                exclusion__schedule__location=template.space.location,
            ).values_list("start_date", "end_date")
        )

        events_created = 0
        for occurrence_start in occurrences:
            occurrence_end = occurrence_start + duration

            # Check if event from this series already exists for this occurrence date
            event_tz = template.space.location.timezone
            occurrence_date = occurrence_start.astimezone(event_tz).date()

            # Skip dates explicitly excluded (e.g. single-deleted occurrences)
            if occurrence_date.isoformat() in excluded_dates:
                continue

            # Skip dates covered by location-level exclusion periods
            if any(
                (start <= occurrence_date <= end if end else occurrence_date == start)
                for start, end in location_exclusion_periods
            ):
                continue

            # Use recurrence_source_date for dedup — survives moves to different times
            existing = Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
                recurrence_source_date=occurrence_date,
            ).exists()

            if existing:
                continue

            event = Event.objects.create(
                service=template.service,
                start_datetime=occurrence_start,
                end_datetime=occurrence_end,
                space=template.space,
                capacity=template.capacity,
                group=template.group,
                status=template.status,
                notes=template.notes,
                recurrence_freq=template.recurrence_freq,
                recurrence_interval=template.recurrence_interval,
                recurrence_byweekday=template.recurrence_byweekday,
                recurrence_bymonthday=template.recurrence_bymonthday,
                recurrence_bysetpos=template.recurrence_bysetpos,
                recurrence_byweekday_monthly=template.recurrence_byweekday_monthly,
                recurrence_until=template.recurrence_until,
                recurrence_template=template,
                is_recurrence_template=False,
                recurrence_source_date=occurrence_date,
            )
            event.staff.set(template.staff.all())
            events_created += 1

        return events_created

    def _calculate_occurrences(self, days_ahead=7, start_date=None, end_date=None) -> list:
        """
        Calculate occurrence datetimes based on recurrence settings.

        Args:
            days_ahead: How many days ahead to generate (default: 7).
                        Ignored if start_date/end_date provided.
            start_date: Optional start date for the range (defaults to now)
            end_date: Optional end date for the range (defaults to now + days_ahead)

        Returns:
            List of datetime objects for occurrences (excludes the original event)
        """
        from datetime import datetime, time, timedelta

        event_tz = self.event.space.location.timezone
        event_start_local = self.event.start_datetime.astimezone(event_tz)

        if start_date and end_date:
            start_dt = datetime.combine(start_date, time.min, tzinfo=event_tz)
            end_dt = datetime.combine(end_date, time.max, tzinfo=event_tz)
        else:
            start_dt = timezone.now()
            end_date_only = (timezone.now() + timedelta(days=days_ahead)).date()
            end_dt = datetime.combine(end_date_only, time.max, tzinfo=event_tz)

        if self.event.recurrence_until:
            end_dt = min(end_dt, self.event.recurrence_until)

        weekdays = self.event.recurrence_byweekday if self.event.recurrence_byweekday else None

        bymonthday = self.event.recurrence_bymonthday
        bysetpos = self.event.recurrence_bysetpos
        byweekday_monthly = self.event.recurrence_byweekday_monthly

        if bysetpos is not None and byweekday_monthly is not None:
            weekdays = byweekday_monthly

        rule = rrule.rrule(
            freq=self.event.recurrence_freq,
            interval=self.event.recurrence_interval,
            dtstart=event_start_local,
            until=end_dt,
            byweekday=weekdays,
            bymonthday=bymonthday,
            bysetpos=bysetpos,
        )

        if start_date and end_date:
            occurrences = rule.between(start_dt, end_dt, inc=True)
        else:
            occurrences = list(rule)
            if occurrences and occurrences[0] == event_start_local and not self.event.is_recurrence_template:
                occurrences = occurrences[1:]

        return occurrences

    # ------------------------------------------------------------------
    # Projection helpers (calendar views)
    # ------------------------------------------------------------------

    @staticmethod
    def get_events_with_recurrence_projections(queryset, start_date, end_date):
        """
        Get both existing events and projected recurring events for a date range.

        Returns:
            List combining real Event objects and ProjectedEvent objects,
            sorted by start_datetime
        """
        from ..models import Event

        events = queryset.filter(is_recurrence_template=False).annotate(is_projected=Value(False))

        active_templates = Event.objects.active_recurrence_templates()

        # No projections in the past — clamp projection start to today
        today = timezone.now().date()
        projection_start = max(start_date, today)

        projected_events = []
        if projection_start <= end_date:
            from ..models import EventGenerationScheduleExclusionPeriod

            for template in active_templates:
                occurrences = EventService(template)._calculate_occurrences(
                    start_date=projection_start, end_date=end_date
                )
                duration = template.end_datetime - template.start_datetime
                excluded_dates = set(template.recurrence_excluded_dates or [])

                # Load location-level exclusion periods
                location_exclusion_periods = list(
                    EventGenerationScheduleExclusionPeriod.objects.filter(
                        exclusion__schedule__location=template.space.location,
                    ).values_list("start_date", "end_date")
                )

                for occurrence_start in occurrences:
                    event_tz = template.space.location.timezone
                    occurrence_date = occurrence_start.astimezone(event_tz).date()

                    # Skip dates explicitly excluded (e.g. single-deleted occurrences)
                    if occurrence_date.isoformat() in excluded_dates:
                        continue

                    # Skip dates covered by location-level exclusion periods
                    if any(
                        (start <= occurrence_date <= end if end else occurrence_date == start)
                        for start, end in location_exclusion_periods
                    ):
                        continue

                    # Use recurrence_source_date for dedup — survives moves
                    if Event.objects.filter(
                        recurrence_template=template,
                        is_recurrence_template=False,
                        recurrence_source_date=occurrence_date,
                    ).exists():
                        continue

                    occurrence_end = occurrence_start + duration
                    projected_events.append(ProjectedEvent(template, occurrence_start, occurrence_end))

        all_events = list(events) + projected_events
        all_events.sort(key=lambda e: e.start_datetime)
        return all_events

    # ------------------------------------------------------------------
    # Conflict checks (used by operations)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_staff_availability(
        event: "Event",
        start_datetime,
        end_datetime,
        staff_members,
        events_to_exclude=None,
    ) -> ValidationResult:
        """
        Check staff members for overlapping event assignments.

        Returns a ValidationResult with a warning (not error) for each conflict.
        """
        from ..models import Event

        result = ValidationResult()

        if not staff_members:
            return result

        staff_ids = [s.pk if hasattr(s, "pk") else s for s in staff_members]
        if not staff_ids:
            return result

        exclude_pks = events_to_exclude if events_to_exclude else []

        conflicting_events = (
            Event.objects.filter(
                staff__id__in=staff_ids,
                start_datetime__lt=end_datetime,
                end_datetime__gt=start_datetime,
            )
            .exclude(pk__in=exclude_pks)
            .prefetch_related("staff", "space__location")
        )

        if conflicting_events.exists():
            conflict = conflicting_events.first()
            conflicting_staff = conflict.staff.filter(id__in=staff_ids).first()
            event_tz = conflict.space.location.timezone
            conflict_start_local = conflict.start_datetime.astimezone(event_tz)
            conflict_end_local = conflict.end_datetime.astimezone(event_tz)

            result.add_warning(
                f"Staff member '{conflicting_staff.user.get_full_name()}' is already "
                f"assigned to another event: {conflict.service.name} "
                f"({conflict_start_local.strftime('%Y-%m-%d %H:%M')} - "
                f"{conflict_end_local.strftime('%H:%M')}) in {conflict.space.name}.",
                field="staff",
            )

        return result
