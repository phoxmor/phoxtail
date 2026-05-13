"""
Admin operation: delete an existing event (single, this-and-future, all-in-series).
"""

from typing import TYPE_CHECKING

from django.db import transaction

from ...validation import ValidationResult

if TYPE_CHECKING:
    from ....models import Event
    from ...base import EventService


class EventServiceAdminDelete:
    """
    Admin domain operation for event deletion.

    Supports three scopes:
      - THIS_EVENT_ONLY (default)
      - THIS_AND_FUTURE_EVENTS
      - ALL_EVENTS_IN_SERIES
    """

    def __init__(self, service: "EventService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, delete_scope: str | None = None) -> ValidationResult:
        from ....constants import EventUpdateScope

        event = self.service.event
        result = ValidationResult()

        if delete_scope is None or delete_scope not in EventUpdateScope.values:
            delete_scope = EventUpdateScope.THIS_EVENT_ONLY

        # Block single-delete on template events — CASCADE would destroy all children
        if event.is_recurrence_template and delete_scope == EventUpdateScope.THIS_EVENT_ONLY:
            result.add_error(
                "Cannot delete a series template directly. "
                "Use 'All events in series' to delete the entire series, "
                "or delete individual events instead."
            )
            return result

        events_to_check = self._get_events_for_scope(event, delete_scope)
        self._validate_no_active_reservations(result, events_to_check)

        return result

    # ------------------------------------------------------------------
    # Perform
    # ------------------------------------------------------------------

    def perform(self, delete_scope: str | None = None) -> int:
        from ....constants import EventUpdateScope

        event = self.service.event

        if delete_scope is None or delete_scope not in EventUpdateScope.values:
            delete_scope = EventUpdateScope.THIS_EVENT_ONLY

        if not event.recurrence_template and not event.is_recurrence_template:
            return self._perform_single_delete(event)

        if delete_scope == EventUpdateScope.THIS_EVENT_ONLY:
            return self._perform_single_delete(event)
        elif delete_scope == EventUpdateScope.THIS_AND_FUTURE_EVENTS:
            return self._perform_this_and_future_delete(event)
        elif delete_scope == EventUpdateScope.ALL_EVENTS_IN_SERIES:
            return self._perform_all_in_series_delete(event)

        return 0

    def execute(
        self,
        delete_scope: str | None = None,
        force: bool = True,
    ) -> int:
        self.authorize()
        result = self.validate(delete_scope=delete_scope)
        result.raise_if_errors()
        if not force:
            result.raise_if_warnings()
        return self.perform(delete_scope=delete_scope)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_events_for_scope(self, event: "Event", delete_scope: str):
        """Return the queryset of events that would be affected by the delete scope."""
        from ....constants import EventUpdateScope
        from ....models import Event

        if not event.recurrence_template and not event.is_recurrence_template:
            return Event.objects.filter(pk=event.pk)

        if delete_scope == EventUpdateScope.THIS_EVENT_ONLY:
            return Event.objects.filter(pk=event.pk)

        template = event if event.is_recurrence_template else event.recurrence_template

        if delete_scope == EventUpdateScope.THIS_AND_FUTURE_EVENTS:
            return Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
                start_datetime__gte=event.start_datetime,
            )
        elif delete_scope == EventUpdateScope.ALL_EVENTS_IN_SERIES:
            # Include both series instances and the template itself
            from django.db.models import Q

            return Event.objects.filter(
                Q(recurrence_template=template, is_recurrence_template=False) | Q(pk=template.pk)
            )

        return Event.objects.filter(pk=event.pk)

    def _validate_no_active_reservations(self, result: ValidationResult, events):
        """Add a hard error if any event in the set has active reservations."""
        from phoxtail.booking.reservations.constants import ReservationStatus
        from phoxtail.booking.reservations.models import Reservation

        events_with_reservations = (
            Reservation.objects.filter(
                event__in=events,
            )
            .exclude(
                status=ReservationStatus.CANCELLED,
            )
            .values_list("event_id", flat=True)
            .distinct()
        )

        count = events_with_reservations.count()
        if count > 0:
            if count == 1:
                result.add_error(
                    "Cannot delete: 1 event has active reservations. Cancel or remove reservations before deleting."
                )
            else:
                result.add_error(
                    f"Cannot delete: {count} events have active reservations. "
                    "Cancel or remove reservations before deleting."
                )

    def _perform_single_delete(self, event: "Event") -> int:
        with transaction.atomic():
            # If this event belongs to a series, record its source date
            # on the template so projection and generation skip this occurrence
            if event.recurrence_template and event.recurrence_source_date:
                template = event.recurrence_template
                excluded = list(template.recurrence_excluded_dates or [])
                source_date_str = event.recurrence_source_date.isoformat()
                if source_date_str not in excluded:
                    excluded.append(source_date_str)
                    template.recurrence_excluded_dates = excluded
                    template.save(update_fields=["recurrence_excluded_dates"])

            event.delete()
            return 1

    def _perform_this_and_future_delete(self, event: "Event") -> int:
        from datetime import timedelta

        from ....models import Event

        with transaction.atomic():
            template = event if event.is_recurrence_template else event.recurrence_template

            original_start_datetime = Event.objects.get(pk=event.pk).start_datetime

            future_events = Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
                start_datetime__gte=original_start_datetime,
            )

            count = future_events.count()
            future_events.delete()

            # End the series just before the deleted event so recurrence
            # generation won't regenerate at the boundary datetime
            template.recurrence_until = original_start_datetime - timedelta(seconds=1)
            template.save(update_fields=["recurrence_until"])

            return count

    def _perform_all_in_series_delete(self, event: "Event") -> int:
        from ....models import Event

        with transaction.atomic():
            template = event if event.is_recurrence_template else event.recurrence_template

            # Delete all generated events in the series
            series_events = Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            )

            count = series_events.count()
            series_events.delete()

            # Also delete the template itself
            template.delete()
            return count + 1
