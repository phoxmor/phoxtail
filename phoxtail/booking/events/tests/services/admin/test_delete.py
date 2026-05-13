"""
Tests for EventServiceAdminDelete — the admin event deletion operation.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

UTC = datetime.UTC

from phoxtail.booking.events.constants import EventUpdateScope
from phoxtail.booking.events.models import Event
from phoxtail.booking.events.services import EventService
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.tests.factories import ReservationFactory

from ...factories import EventFactory, RecurringTemplateFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Happy path — single event
# ---------------------------------------------------------------------------


class TestDeleteSingleEvent:
    @freeze_time("2024-06-03 08:00:00")
    def test_deletes_single_event(self, service, space):
        event = EventFactory(service=service, space=space)
        event_pk = event.pk

        deleted = EventService(event).admin.delete()

        assert deleted == 1
        assert not Event.objects.filter(pk=event_pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_deletes_single_recurring_event_with_this_event_only_scope(self, service, space):
        template = RecurringTemplateFactory(service=service, space=space)
        event1 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
        )
        event2 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
        )

        deleted = EventService(event1).admin.delete(delete_scope=EventUpdateScope.THIS_EVENT_ONLY)

        assert deleted == 1
        assert not Event.objects.filter(pk=event1.pk).exists()
        assert Event.objects.filter(pk=event2.pk).exists()
        assert Event.objects.filter(pk=template.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_single_delete_records_excluded_date_on_template(self, service, space):
        """Deleting a single series event should record its source date
        on the template's recurrence_excluded_dates."""
        template = RecurringTemplateFactory(service=service, space=space)
        event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            recurrence_source_date=datetime.date(2024, 6, 3),
        )

        EventService(event).admin.delete(delete_scope=EventUpdateScope.THIS_EVENT_ONLY)

        template.refresh_from_db()
        assert "2024-06-03" in template.recurrence_excluded_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_single_delete_excluded_date_prevents_regeneration(self, service, space):
        """After single-deleting a series event, the generation task should
        not recreate an event on the excluded date."""
        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 11, 0), UTC),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )

        EventService(event).admin.delete(delete_scope=EventUpdateScope.THIS_EVENT_ONLY)

        # Generation should skip the excluded date
        count = EventService(template).generate_recurring_events(days_ahead=30)
        generated_dates = list(
            Event.objects.filter(
                recurrence_template=template,
                is_recurrence_template=False,
            ).values_list("recurrence_source_date", flat=True)
        )
        assert datetime.date(2024, 6, 10) not in generated_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_single_delete_excluded_date_prevents_projection(self, service, space):
        """After single-deleting a series event, projection should not
        show a projected event on the excluded date."""
        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 11, 0), UTC),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )

        EventService(event).admin.delete(delete_scope=EventUpdateScope.THIS_EVENT_ONLY)

        # Projection should skip the excluded date
        all_events = EventService.get_events_with_recurrence_projections(
            Event.objects.all(),
            start_date=datetime.date(2024, 6, 3),
            end_date=datetime.date(2024, 6, 17),
        )
        projected_dates = [e.start_datetime.date() for e in all_events if getattr(e, "is_projected", False)]
        assert datetime.date(2024, 6, 10) not in projected_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_single_delete_without_source_date_does_not_record_exclusion(self, service, space):
        """If the event has no recurrence_source_date, no exclusion is recorded."""
        template = RecurringTemplateFactory(service=service, space=space)
        event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            recurrence_source_date=None,
        )

        EventService(event).admin.delete(delete_scope=EventUpdateScope.THIS_EVENT_ONLY)

        template.refresh_from_db()
        assert template.recurrence_excluded_dates == []


# ---------------------------------------------------------------------------
# Happy path — this and future events
# ---------------------------------------------------------------------------


class TestDeleteThisAndFutureEvents:
    @freeze_time("2024-06-03 08:00:00")
    def test_deletes_future_events_and_ends_series(self, service, space):
        template = RecurringTemplateFactory(service=service, space=space)
        past_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 5, 27, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 5, 27, 11, 0), UTC),
        )
        current_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        future_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 11, 0), UTC),
        )

        deleted = EventService(current_event).admin.delete(delete_scope=EventUpdateScope.THIS_AND_FUTURE_EVENTS)

        assert deleted == 2
        assert Event.objects.filter(pk=past_event.pk).exists()
        assert not Event.objects.filter(pk=current_event.pk).exists()
        assert not Event.objects.filter(pk=future_event.pk).exists()

        # Template should still exist with recurrence_until set just before
        # the deleted event's start_datetime
        template.refresh_from_db()
        expected_until = current_event.start_datetime - datetime.timedelta(seconds=1)
        assert template.recurrence_until == expected_until

    @freeze_time("2024-06-03 08:00:00")
    def test_recurrence_until_prevents_regeneration_at_boundary(self, service, space):
        """After this-and-future delete, recurrence generation should NOT
        regenerate events at or after the deleted boundary datetime."""
        template = RecurringTemplateFactory(
            service=service,
            space=space,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        # Pre-existing event for June 3 (template's own start date)
        EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_source_date=datetime.date(2024, 6, 3),
        )
        event_to_delete = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 11, 0), UTC),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )

        EventService(event_to_delete).admin.delete(delete_scope=EventUpdateScope.THIS_AND_FUTURE_EVENTS)

        template.refresh_from_db()
        # recurrence_until is now just before June 10 — no new events
        # should be generated (June 3 already exists via source_date dedup)
        count = EventService(template).generate_recurring_events(days_ahead=30)
        assert count == 0


# ---------------------------------------------------------------------------
# Happy path — all events in series
# ---------------------------------------------------------------------------


class TestDeleteAllEventsInSeries:
    @freeze_time("2024-06-03 08:00:00")
    def test_deletes_all_events_and_template(self, service, space):
        template = RecurringTemplateFactory(service=service, space=space)
        event1 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
        )
        event2 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
        )

        deleted = EventService(event1).admin.delete(delete_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES)

        assert deleted == 3  # 2 events + 1 template
        assert not Event.objects.filter(pk=event1.pk).exists()
        assert not Event.objects.filter(pk=event2.pk).exists()
        assert not Event.objects.filter(pk=template.pk).exists()


# ---------------------------------------------------------------------------
# Non-recurring event with bulk scope falls back to single delete
# ---------------------------------------------------------------------------


class TestDeleteNonRecurringWithScope:
    @freeze_time("2024-06-03 08:00:00")
    def test_non_recurring_event_ignores_scope(self, service, space):
        event = EventFactory(service=service, space=space)
        event_pk = event.pk

        deleted = EventService(event).admin.delete(delete_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES)

        assert deleted == 1
        assert not Event.objects.filter(pk=event_pk).exists()


# ---------------------------------------------------------------------------
# Template event protection
# ---------------------------------------------------------------------------


class TestDeleteTemplateProtection:
    @freeze_time("2024-06-03 08:00:00")
    def test_single_delete_on_template_event_is_blocked(self, service, space):
        """Deleting a template with THIS_EVENT_ONLY would CASCADE-destroy
        all child events. This must be a hard error."""
        template = RecurringTemplateFactory(service=service, space=space)
        child = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
        )

        with pytest.raises(ValidationError, match="Cannot delete a series template"):
            EventService(template).admin.delete(delete_scope=EventUpdateScope.THIS_EVENT_ONLY)

        # Template and child must still exist
        assert Event.objects.filter(pk=template.pk).exists()
        assert Event.objects.filter(pk=child.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_template_default_scope_is_blocked(self, service, space):
        """Default scope is THIS_EVENT_ONLY, which must be blocked for templates."""
        template = RecurringTemplateFactory(service=service, space=space)

        with pytest.raises(ValidationError, match="Cannot delete a series template"):
            EventService(template).admin.delete()

    @freeze_time("2024-06-03 08:00:00")
    def test_all_in_series_from_template_event_succeeds(self, service, space):
        """ALL_EVENTS_IN_SERIES should work even when called on the template itself."""
        template = RecurringTemplateFactory(service=service, space=space)
        child = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
        )

        deleted = EventService(template).admin.delete(delete_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES)

        assert deleted == 2  # 1 child + 1 template
        assert not Event.objects.filter(pk=template.pk).exists()
        assert not Event.objects.filter(pk=child.pk).exists()


# ---------------------------------------------------------------------------
# Hard errors — active reservations (all non-cancelled statuses)
# ---------------------------------------------------------------------------


class TestDeleteBlockedByReservations:
    @freeze_time("2024-06-03 08:00:00")
    def test_single_event_with_confirmed_reservation_raises(self, service, space):
        event = EventFactory(service=service, space=space)
        ReservationFactory(event=event, status=ReservationStatus.CONFIRMED)

        with pytest.raises(ValidationError, match="active reservations"):
            EventService(event).admin.delete()

        assert Event.objects.filter(pk=event.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_single_event_with_completed_reservation_raises(self, service, space):
        event = EventFactory(service=service, space=space)
        ReservationFactory(event=event, status=ReservationStatus.COMPLETED)

        with pytest.raises(ValidationError, match="active reservations"):
            EventService(event).admin.delete()

        assert Event.objects.filter(pk=event.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_single_event_with_waitlisted_reservation_raises(self, service, space):
        event = EventFactory(service=service, space=space)
        ReservationFactory(event=event, status=ReservationStatus.WAITLISTED)

        with pytest.raises(ValidationError, match="active reservations"):
            EventService(event).admin.delete()

        assert Event.objects.filter(pk=event.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_single_event_with_no_show_reservation_raises(self, service, space):
        event = EventFactory(service=service, space=space)
        ReservationFactory(event=event, status=ReservationStatus.NO_SHOW)

        with pytest.raises(ValidationError, match="active reservations"):
            EventService(event).admin.delete()

        assert Event.objects.filter(pk=event.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_single_event_with_cancelled_reservation_succeeds(self, service, space):
        event = EventFactory(service=service, space=space)
        ReservationFactory(event=event, status=ReservationStatus.CANCELLED)

        deleted = EventService(event).admin.delete()

        assert deleted == 1
        assert not Event.objects.filter(pk=event.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_series_delete_blocked_when_any_event_has_reservation(self, service, space):
        template = RecurringTemplateFactory(service=service, space=space)
        event1 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
        )
        event2 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
        )
        # Only event2 has a reservation
        ReservationFactory(event=event2, status=ReservationStatus.CONFIRMED)

        with pytest.raises(ValidationError, match="1 event has active reservations"):
            EventService(event1).admin.delete(delete_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES)

        # Both events and template should still exist
        assert Event.objects.filter(pk=event1.pk).exists()
        assert Event.objects.filter(pk=event2.pk).exists()
        assert Event.objects.filter(pk=template.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_future_delete_blocked_by_reservation_on_future_event(self, service, space):
        template = RecurringTemplateFactory(service=service, space=space)
        EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 5, 27, 10, 0), UTC),
        )
        future_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
        )
        ReservationFactory(event=future_event, status=ReservationStatus.CONFIRMED)

        with pytest.raises(ValidationError, match="active reservations"):
            EventService(future_event).admin.delete(delete_scope=EventUpdateScope.THIS_AND_FUTURE_EVENTS)

    @freeze_time("2024-06-03 08:00:00")
    def test_future_delete_not_blocked_by_reservation_on_past_event(self, service, space):
        """Past events with reservations shouldn't block deleting future events."""
        template = RecurringTemplateFactory(service=service, space=space)
        past_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 5, 27, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 5, 27, 11, 0), UTC),
        )
        future_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 11, 0), UTC),
        )
        # Reservation is on the past event, not the future one
        ReservationFactory(event=past_event, status=ReservationStatus.CONFIRMED)

        deleted = EventService(future_event).admin.delete(delete_scope=EventUpdateScope.THIS_AND_FUTURE_EVENTS)

        assert deleted == 1
        assert Event.objects.filter(pk=past_event.pk).exists()
        assert not Event.objects.filter(pk=future_event.pk).exists()

    @freeze_time("2024-06-03 08:00:00")
    def test_multiple_events_with_reservations_shows_count(self, service, space):
        template = RecurringTemplateFactory(service=service, space=space)
        event1 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
        )
        event2 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
        )
        ReservationFactory(event=event1, status=ReservationStatus.CONFIRMED)
        ReservationFactory(event=event2, status=ReservationStatus.CONFIRMED)

        with pytest.raises(ValidationError, match="2 events have active reservations"):
            EventService(event1).admin.delete(delete_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES)


# ---------------------------------------------------------------------------
# Validation-only entry point
# ---------------------------------------------------------------------------


class TestDeleteValidation:
    @freeze_time("2024-06-03 08:00:00")
    def test_validate_returns_error_for_reservations(self, service, space):
        event = EventFactory(service=service, space=space)
        ReservationFactory(event=event, status=ReservationStatus.CONFIRMED)

        result = EventService(event).admin.validate_delete()

        assert result.has_errors
        assert "active reservations" in result.errors[0].message

    @freeze_time("2024-06-03 08:00:00")
    def test_validate_returns_clean_result_for_no_reservations(self, service, space):
        event = EventFactory(service=service, space=space)

        result = EventService(event).admin.validate_delete()

        assert result.is_valid
        assert not result.has_warnings

    @freeze_time("2024-06-03 08:00:00")
    def test_validate_template_single_delete_returns_error(self, service, space):
        template = RecurringTemplateFactory(service=service, space=space)

        result = EventService(template).admin.validate_delete(delete_scope=EventUpdateScope.THIS_EVENT_ONLY)

        assert result.has_errors
        assert "series template" in result.errors[0].message

    @freeze_time("2024-06-03 08:00:00")
    def test_validate_scoped_series_with_reservation(self, service, space):
        """validate_delete with ALL_EVENTS_IN_SERIES should check all events."""
        template = RecurringTemplateFactory(service=service, space=space)
        EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC),
        )
        event2 = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
        )
        ReservationFactory(event=event2, status=ReservationStatus.COMPLETED)

        result = EventService(event2).admin.validate_delete(delete_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES)

        assert result.has_errors
        assert "active reservations" in result.errors[0].message

    @freeze_time("2024-06-03 08:00:00")
    def test_validate_this_and_future_ignores_past_reservations(self, service, space):
        """validate_delete with THIS_AND_FUTURE should only check future events."""
        template = RecurringTemplateFactory(service=service, space=space)
        past_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 5, 27, 10, 0), UTC),
        )
        future_event = EventFactory(
            service=service,
            space=space,
            recurrence_template=template,
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 10, 10, 0), UTC),
        )
        ReservationFactory(event=past_event, status=ReservationStatus.CONFIRMED)

        result = EventService(future_event).admin.validate_delete(delete_scope=EventUpdateScope.THIS_AND_FUTURE_EVENTS)

        assert result.is_valid
