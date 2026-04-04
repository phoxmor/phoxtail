"""
Tests for EventServiceAdminCreate — the admin event creation operation.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

UTC = datetime.UTC

from phoxtail.booking.events.constants import EventStatus, RecurrenceFrequency
from phoxtail.booking.events.models import Event
from phoxtail.booking.events.services import EventService

from ...factories import EventFactory, SpaceFactory, StaffFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCreateHappyPath:
    @freeze_time("2024-06-03 08:00:00")
    def test_creates_event_with_correct_fields(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        event = EventService().admin.create(
            service=service,
            start_datetime=start,
            end_datetime=end,
            space=space,
            capacity=10,
            status=EventStatus.CONFIRMED,
        )
        assert event.pk is not None
        assert event.service == service
        assert event.space == space
        assert event.capacity == 10
        assert event.start_datetime == start
        assert event.end_datetime == end

    @freeze_time("2024-06-03 08:00:00")
    def test_recurring_event_sets_is_recurrence_template(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 3, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC)
        event = EventService().admin.create(
            service=service,
            start_datetime=start,
            end_datetime=end,
            space=space,
            capacity=10,
            recurrence_freq=RecurrenceFrequency.WEEKLY,
            recurrence_interval=1,
            recurrence_byweekday=[0],
            recurrence_until=start + datetime.timedelta(days=30),
        )
        assert event.is_recurrence_template is True

    @freeze_time("2024-06-03 08:00:00")
    def test_non_recurring_event_is_not_template(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        event = EventService().admin.create(
            service=service,
            start_datetime=start,
            end_datetime=end,
            space=space,
            capacity=10,
        )
        assert event.is_recurrence_template is False

    @freeze_time("2024-06-03 08:00:00")
    def test_staff_assigned_via_m2m(self, service, space):
        staff1 = StaffFactory()
        staff2 = StaffFactory()
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        event = EventService().admin.create(
            service=service,
            start_datetime=start,
            end_datetime=end,
            space=space,
            capacity=10,
            staff=[staff1, staff2],
        )
        assert set(event.staff.all()) == {staff1, staff2}

    @freeze_time("2024-06-03 08:00:00")
    def test_persists_to_database(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        event = EventService().admin.create(
            service=service,
            start_datetime=start,
            end_datetime=end,
            space=space,
            capacity=10,
        )
        assert Event.objects.filter(pk=event.pk).exists()


# ---------------------------------------------------------------------------
# Validation errors (hard)
# ---------------------------------------------------------------------------


class TestCreateValidationErrors:
    def test_end_before_start_raises(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        with pytest.raises(ValidationError):
            EventService().admin.create(
                service=service,
                start_datetime=start,
                end_datetime=end,
                space=space,
                capacity=10,
            )

    def test_duration_exceeds_24_hours_raises(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = start + datetime.timedelta(hours=25)
        with pytest.raises(ValidationError):
            EventService().admin.create(
                service=service,
                start_datetime=start,
                end_datetime=end,
                space=space,
                capacity=10,
            )

    def test_recurrence_until_before_start_raises(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        with pytest.raises(ValidationError):
            EventService().admin.create(
                service=service,
                start_datetime=start,
                end_datetime=end,
                space=space,
                capacity=10,
                recurrence_freq=RecurrenceFrequency.WEEKLY,
                recurrence_interval=1,
                recurrence_byweekday=[0],
                recurrence_until=start - datetime.timedelta(days=1),
            )


# ---------------------------------------------------------------------------
# Validation warnings (soft — force=False triggers raise)
# ---------------------------------------------------------------------------


class TestCreateValidationWarnings:
    @freeze_time("2024-06-03 08:00:00")
    def test_space_time_conflict_raises_when_not_forced(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        # Create existing event in the same slot
        EventFactory(space=space, start_datetime=start, end_datetime=end)

        with pytest.raises(ValidationError):
            EventService().admin.create(
                force=False,
                service=service,
                start_datetime=start,
                end_datetime=end,
                space=space,
                capacity=10,
            )

    @freeze_time("2024-06-03 08:00:00")
    def test_space_time_conflict_allowed_when_forced(self, service, space):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        EventFactory(space=space, start_datetime=start, end_datetime=end)

        # force=True (default) should succeed
        event = EventService().admin.create(
            service=service,
            start_datetime=start,
            end_datetime=end,
            space=space,
            capacity=10,
        )
        assert event.pk is not None

    @freeze_time("2024-06-03 08:00:00")
    def test_staff_double_booking_raises_when_not_forced(self, service, space):
        staff = StaffFactory()
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        existing = EventFactory(
            space=SpaceFactory(),
            start_datetime=start,
            end_datetime=end,
        )
        existing.staff.add(staff)

        with pytest.raises(ValidationError):
            EventService().admin.create(
                force=False,
                service=service,
                start_datetime=start,
                end_datetime=end,
                space=space,
                capacity=10,
                staff=[staff],
            )
