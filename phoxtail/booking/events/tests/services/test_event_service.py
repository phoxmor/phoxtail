"""
Tests for EventService — the core business logic layer.

These tests verify the service in isolation by constructing model instances
directly via factories (bypassing the creation service), which gives full
control over the exact state under test.
"""

import datetime

import pytest
from django.utils import timezone
from freezegun import freeze_time

from phoxtail.booking.core.models import BookingGroup

UTC = datetime.UTC

from phoxtail.booking.events.constants import EventStatus, RecurrenceFrequency
from phoxtail.booking.events.services import EventService
from phoxtail.booking.events.services.projected import ProjectedEvent
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.models import Reservation
from phoxtail.booking.subscriptions.tests.factories import (
    UserFactory,
)

from ..factories import (
    EventFactory,
    RecurringTemplateFactory,
    SpaceFactory,
    StaffFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# get_reservation_count
# ---------------------------------------------------------------------------


class TestGetReservationCount:
    def test_zero_reservations(self, event):
        assert EventService(event).get_reservation_count() == 0

    def test_counts_confirmed_and_completed(self, event, user):
        from phoxtail.booking.subscriptions.tests.factories import SubscriptionFactory

        sub = SubscriptionFactory(user=user)
        Reservation.objects.create(
            user=user,
            event=event,
            subscription=sub,
            status=ReservationStatus.CONFIRMED,
        )
        other_user = UserFactory()
        sub2 = SubscriptionFactory(user=other_user)
        Reservation.objects.create(
            user=other_user,
            event=event,
            subscription=sub2,
            status=ReservationStatus.COMPLETED,
        )
        assert EventService(event).get_reservation_count() == 2

    def test_excludes_cancelled_and_waitlisted(self, event):
        from phoxtail.booking.subscriptions.tests.factories import SubscriptionFactory

        u1 = UserFactory()
        u2 = UserFactory()
        sub1 = SubscriptionFactory(user=u1)
        sub2 = SubscriptionFactory(user=u2)
        Reservation.objects.create(
            user=u1,
            event=event,
            subscription=sub1,
            status=ReservationStatus.CANCELLED,
        )
        Reservation.objects.create(
            user=u2,
            event=event,
            subscription=sub2,
            status=ReservationStatus.WAITLISTED,
        )
        assert EventService(event).get_reservation_count() == 0


# ---------------------------------------------------------------------------
# get_available_spots_count
# ---------------------------------------------------------------------------


class TestGetAvailableSpots:
    def test_full_capacity_available(self, event):
        assert EventService(event).get_available_spots_count() == event.capacity

    def test_partial_availability(self, event):
        from phoxtail.booking.subscriptions.tests.factories import SubscriptionFactory

        u = UserFactory()
        sub = SubscriptionFactory(user=u)
        Reservation.objects.create(
            user=u,
            event=event,
            subscription=sub,
            status=ReservationStatus.CONFIRMED,
        )
        assert EventService(event).get_available_spots_count() == event.capacity - 1

    def test_at_capacity_returns_zero(self):
        event = EventFactory(capacity=1)
        from phoxtail.booking.subscriptions.tests.factories import SubscriptionFactory

        u = UserFactory()
        sub = SubscriptionFactory(user=u)
        Reservation.objects.create(
            user=u,
            event=event,
            subscription=sub,
            status=ReservationStatus.CONFIRMED,
        )
        assert EventService(event).get_available_spots_count() == 0


# ---------------------------------------------------------------------------
# get_is_full
# ---------------------------------------------------------------------------


class TestGetIsFull:
    def test_not_full(self, event):
        assert EventService(event).get_is_full() is False

    def test_exactly_full(self):
        event = EventFactory(capacity=1)
        from phoxtail.booking.subscriptions.tests.factories import SubscriptionFactory

        u = UserFactory()
        sub = SubscriptionFactory(user=u)
        Reservation.objects.create(
            user=u,
            event=event,
            subscription=sub,
            status=ReservationStatus.CONFIRMED,
        )
        assert EventService(event).get_is_full() is True


# ---------------------------------------------------------------------------
# is_cancelled / is_unpublished
# ---------------------------------------------------------------------------


class TestIsCancelled:
    def test_confirmed_is_not_cancelled(self, event):
        assert EventService(event).is_cancelled() is False

    def test_cancelled_event(self):
        event = EventFactory(status=EventStatus.CANCELLED)
        assert EventService(event).is_cancelled() is True


class TestIsUnpublished:
    def test_confirmed_is_not_unpublished(self, event):
        assert EventService(event).is_unpublished() is False

    def test_unpublished_event(self):
        event = EventFactory(status=EventStatus.UNPUBLISHED)
        assert EventService(event).is_unpublished() is True


# ---------------------------------------------------------------------------
# user_can_access_event
# ---------------------------------------------------------------------------


class TestUserCanAccessEvent:
    def test_no_group_open_to_all(self, event, user):
        assert event.group is None
        assert EventService(event).user_can_access_event(user) is True

    def test_user_in_group_can_access(self, event, user):
        group = BookingGroup.objects.create(name="VIP")
        group.members.add(user)
        event.group = group
        event.save()
        assert EventService(event).user_can_access_event(user) is True

    def test_user_not_in_group_denied(self, event, user):
        group = BookingGroup.objects.create(name="VIP")
        event.group = group
        event.save()
        assert EventService(event).user_can_access_event(user) is False


# ---------------------------------------------------------------------------
# generate_recurring_events
# ---------------------------------------------------------------------------


class TestGenerateRecurringEvents:
    @freeze_time("2024-06-03 08:00:00")  # Monday
    def test_non_recurring_returns_zero(self):
        event = EventFactory(recurrence_freq=None)
        assert EventService(event).generate_recurring_events() == 0

    @freeze_time("2024-06-03 08:00:00")  # Monday
    def test_weekly_creates_correct_count(self):
        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],  # Monday
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 24, 23, 59), UTC
            ),
        )
        count = EventService(template).generate_recurring_events(days_ahead=30)
        # Template is is_recurrence_template=True so its own date is included:
        # occurrences on June 3, 10, 17, 24
        assert count == 4

    @freeze_time("2024-06-03 08:00:00")
    def test_sets_recurrence_source_date(self):
        from phoxtail.booking.events.models import Event

        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 23, 59), UTC
            ),
        )
        EventService(template).generate_recurring_events(days_ahead=30)

        generated = Event.objects.filter(
            recurrence_template=template, is_recurrence_template=False
        ).order_by("start_datetime")
        assert generated.count() == 3
        assert generated[0].recurrence_source_date == datetime.date(2024, 6, 3)
        assert generated[1].recurrence_source_date == datetime.date(2024, 6, 10)
        assert generated[2].recurrence_source_date == datetime.date(2024, 6, 17)

    @freeze_time("2024-06-03 08:00:00")
    def test_skips_existing_by_source_date(self):

        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 23, 59), UTC
            ),
        )
        # Pre-create an event for June 10 with matching source_date
        EventFactory(
            space=space,
            service=template.service,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_template=template,
            recurrence_source_date=datetime.date(2024, 6, 10),
        )
        count = EventService(template).generate_recurring_events(days_ahead=30)
        # June 3 and June 17 created; June 10 skipped (existing)
        assert count == 2

    @freeze_time("2024-06-03 08:00:00")
    def test_moved_event_still_prevents_duplicate(self):
        """An event moved to a different time but keeping recurrence_source_date
        should still prevent a duplicate for that occurrence date."""

        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 23, 59), UTC
            ),
        )
        # Moved to 14:00 but source_date still June 10
        EventFactory(
            space=space,
            service=template.service,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 14, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 15, 0), UTC
            ),
            recurrence_template=template,
            recurrence_source_date=datetime.date(2024, 6, 10),
        )
        count = EventService(template).generate_recurring_events(days_ahead=30)
        # June 3 and June 17 created; June 10 skipped (source_date match)
        assert count == 2

    @freeze_time("2024-06-03 08:00:00")
    def test_generates_despite_unrelated_event_in_same_slot(self):
        """An unrelated event in the same space/time does NOT block generation.
        Admins have full freedom to create overlapping schedules (e.g. shadow
        series for selective opening)."""
        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 23, 59), UTC
            ),
        )
        # Unrelated event in the same slot — should NOT block generation
        EventFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
        )
        count = EventService(template).generate_recurring_events(days_ahead=30)
        # All three occurrences created — June 10 is no longer skipped
        assert count == 3

    @freeze_time("2024-06-03 08:00:00")
    def test_respects_recurrence_until(self):
        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 23, 59), UTC
            ),
        )
        count = EventService(template).generate_recurring_events(days_ahead=30)
        # June 3 and June 10 — recurrence_until cuts off before June 17
        assert count == 2


# ---------------------------------------------------------------------------
# get_events_with_recurrence_projections
# ---------------------------------------------------------------------------


class TestGetEventsWithRecurrenceProjections:
    @freeze_time("2024-06-03 08:00:00")
    def test_returns_real_events_when_no_templates(self):
        from phoxtail.booking.events.models import Event

        event = EventFactory(
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 5, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC),
        )
        qs = Event.objects.all()
        result = EventService.get_events_with_recurrence_projections(
            qs,
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        assert len(result) == 1
        assert result[0].pk == event.pk

    @freeze_time("2024-06-03 08:00:00")
    def test_returns_projected_events_for_template(self):
        from phoxtail.booking.events.models import Event

        space = SpaceFactory()
        RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 30, 23, 59), UTC
            ),
        )
        qs = Event.objects.all()
        result = EventService.get_events_with_recurrence_projections(
            qs,
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        projected = [e for e in result if getattr(e, "is_projected", False)]
        assert len(projected) > 0

    @freeze_time("2024-06-03 08:00:00")
    def test_projected_events_are_projected_event_instances(self):
        from phoxtail.booking.events.models import Event

        space = SpaceFactory()
        RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 30, 23, 59), UTC
            ),
        )
        qs = Event.objects.all()
        result = EventService.get_events_with_recurrence_projections(
            qs,
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        projected = [e for e in result if getattr(e, "is_projected", False)]
        for p in projected:
            assert isinstance(p, ProjectedEvent)
            assert p.is_projected is True
            assert p.id is None

    @freeze_time("2024-06-03 08:00:00")
    def test_dedup_no_projection_when_real_event_exists(self):
        from phoxtail.booking.events.models import Event

        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 30, 23, 59), UTC
            ),
        )
        # Create a real event for June 10 — should suppress projection
        EventFactory(
            space=space,
            service=template.service,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_template=template,
            recurrence_source_date=datetime.date(2024, 6, 10),
        )
        qs = Event.objects.all()
        result = EventService.get_events_with_recurrence_projections(
            qs,
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        # No projection should exist for June 10
        projected_dates = [
            e.start_datetime.date() for e in result if getattr(e, "is_projected", False)
        ]
        assert datetime.date(2024, 6, 10) not in projected_dates

    @freeze_time("2024-06-03 08:00:00")
    def test_moved_event_suppresses_projection(self):
        """A real event moved to a different time but keeping source_date
        should suppress the projection for that occurrence."""
        from phoxtail.booking.events.models import Event

        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 30, 23, 59), UTC
            ),
        )
        # Moved to 14:00 but source_date is still June 10
        EventFactory(
            space=space,
            service=template.service,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 14, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 15, 0), UTC
            ),
            recurrence_template=template,
            recurrence_source_date=datetime.date(2024, 6, 10),
        )
        qs = Event.objects.all()
        result = EventService.get_events_with_recurrence_projections(
            qs,
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        projected_dates = [
            e.start_datetime.date() for e in result if getattr(e, "is_projected", False)
        ]
        assert datetime.date(2024, 6, 10) not in projected_dates

    @freeze_time("2024-06-20 08:00:00")
    def test_no_projections_in_the_past(self):
        from phoxtail.booking.events.models import Event

        space = SpaceFactory()
        RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 30, 23, 59), UTC
            ),
        )
        qs = Event.objects.all()
        # Query a past range — should get no projections
        result = EventService.get_events_with_recurrence_projections(
            qs,
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        projected = [e for e in result if getattr(e, "is_projected", False)]
        # All projections should be on or after today (June 20)
        for p in projected:
            assert p.start_datetime.date() >= datetime.date(2024, 6, 20)

    @freeze_time("2024-07-01 08:00:00")
    def test_past_range_returns_only_real_events(self):
        from phoxtail.booking.events.models import Event

        space = SpaceFactory()
        RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_byweekday=[0],
            recurrence_until=timezone.make_aware(
                datetime.datetime(2024, 6, 30, 23, 59), UTC
            ),
        )
        qs = Event.objects.all()
        result = EventService.get_events_with_recurrence_projections(
            qs,
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        projected = [e for e in result if getattr(e, "is_projected", False)]
        assert len(projected) == 0


# ---------------------------------------------------------------------------
# validate_staff_availability
# ---------------------------------------------------------------------------


class TestValidateStaffAvailability:
    @freeze_time("2024-06-03 08:00:00")
    def test_no_conflict_returns_empty(self):
        staff = StaffFactory()
        event = EventFactory()
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        result = EventService.validate_staff_availability(event, start, end, [staff])
        assert result.is_valid
        assert not result.has_warnings

    @freeze_time("2024-06-03 08:00:00")
    def test_overlapping_event_returns_warning(self):
        staff = StaffFactory()
        existing = EventFactory(
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 5, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC),
        )
        existing.staff.add(staff)

        new_event = EventFactory()
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 30), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 30), UTC)
        result = EventService.validate_staff_availability(
            new_event, start, end, [staff]
        )
        assert result.has_warnings
        assert any(w.field == "staff" for w in result.warnings)

    @freeze_time("2024-06-03 08:00:00")
    def test_excluded_events_are_ignored(self):
        staff = StaffFactory()
        existing = EventFactory(
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 5, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC),
        )
        existing.staff.add(staff)

        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 30), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 30), UTC)
        result = EventService.validate_staff_availability(
            existing, start, end, [staff], events_to_exclude=[existing.pk]
        )
        assert not result.has_warnings
