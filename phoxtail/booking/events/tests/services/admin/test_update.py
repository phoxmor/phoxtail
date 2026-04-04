"""
Tests for EventServiceAdminUpdate — single, this-and-future, and all-in-series updates.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

UTC = datetime.UTC

from phoxtail.booking.events.constants import (
    EventUpdateScope,
)
from phoxtail.booking.events.services import EventService
from phoxtail.booking.subscriptions.tests.factories import ServiceFactory

from ...factories import (
    EventFactory,
    RecurringTemplateFactory,
    SpaceFactory,
    StaffFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Single update (THIS_EVENT_ONLY)
# ---------------------------------------------------------------------------


class TestSingleUpdate:
    @freeze_time("2024-06-03 08:00:00")
    def test_updates_fields_on_event(self, event):
        new_service = ServiceFactory()
        updated, count = EventService(event).admin.update(
            update_scope=EventUpdateScope.THIS_EVENT_ONLY,
            service=new_service,
            capacity=20,
        )
        updated.refresh_from_db()
        assert updated.service == new_service
        assert updated.capacity == 20
        assert count == 1

    @freeze_time("2024-06-03 08:00:00")
    def test_sets_staff(self, event):
        staff = StaffFactory()
        updated, count = EventService(event).admin.update(
            update_scope=EventUpdateScope.THIS_EVENT_ONLY,
            staff=[staff],
        )
        assert staff in updated.staff.all()
        assert count == 1

    @freeze_time("2024-06-03 08:00:00")
    def test_returns_event_and_count_tuple(self, event):
        result = EventService(event).admin.update(
            update_scope=EventUpdateScope.THIS_EVENT_ONLY,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[1] == 1


# ---------------------------------------------------------------------------
# This-and-future update
# ---------------------------------------------------------------------------


class TestThisAndFutureUpdate:
    @freeze_time("2024-06-03 08:00:00")
    def test_updates_future_events_only(self):
        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        # Create series instances
        e1 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )
        e2 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 17),
        )
        e3 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 24, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 24, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 24),
        )

        # Update from e2 forward
        updated, count = EventService(e2).admin.update(
            update_scope=EventUpdateScope.THIS_AND_FUTURE_EVENTS,
            capacity=99,
        )
        assert count == 2  # e2 and e3

        e1.refresh_from_db()
        e2.refresh_from_db()
        e3.refresh_from_db()
        assert e1.capacity != 99  # Not touched
        assert e2.capacity == 99
        assert e3.capacity == 99


# ---------------------------------------------------------------------------
# All-in-series update
# ---------------------------------------------------------------------------


class TestAllInSeriesUpdate:
    @freeze_time("2024-06-03 08:00:00")
    def test_updates_all_events_in_series(self):
        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        e1 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )
        e2 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 17, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 17),
        )

        updated, count = EventService(e1).admin.update(
            update_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES,
            capacity=50,
        )
        assert count == 2

        e1.refresh_from_db()
        e2.refresh_from_db()
        assert e1.capacity == 50
        assert e2.capacity == 50


# ---------------------------------------------------------------------------
# Template propagation (this-and-future / all-in-series)
# ---------------------------------------------------------------------------


class TestTemplatePropagation:
    @freeze_time("2024-06-03 08:00:00")
    def test_this_and_future_propagates_to_template(self):
        """Changes applied via this-and-future should also update the template
        so that future generated events inherit the new values."""
        space = SpaceFactory()
        new_space = SpaceFactory(location=space.location, name="Room C")
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        e1 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )

        EventService(e1).admin.update(
            update_scope=EventUpdateScope.THIS_AND_FUTURE_EVENTS,
            capacity=99,
            space=new_space,
        )

        template.refresh_from_db()
        assert template.capacity == 99
        assert template.space == new_space

    @freeze_time("2024-06-03 08:00:00")
    def test_all_in_series_propagates_to_template(self):
        """Changes applied via all-in-series should also update the template."""
        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        e1 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )

        new_service = ServiceFactory()
        EventService(e1).admin.update(
            update_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES,
            service=new_service,
            capacity=50,
        )

        template.refresh_from_db()
        assert template.service == new_service
        assert template.capacity == 50

    @freeze_time("2024-06-03 08:00:00")
    def test_template_propagation_includes_staff(self):
        """Staff changes should also propagate to the template."""
        space = SpaceFactory()
        staff1 = StaffFactory()
        staff2 = StaffFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        template.staff.add(staff1)

        e1 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )

        EventService(e1).admin.update(
            update_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES,
            staff=[staff2],
        )

        template.refresh_from_db()
        assert staff2 in template.staff.all()
        assert staff1 not in template.staff.all()


# ---------------------------------------------------------------------------
# Validation errors (hard)
# ---------------------------------------------------------------------------


class TestUpdateValidationErrors:
    def test_end_before_start_raises(self, event):
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        with pytest.raises(ValidationError):
            EventService(event).admin.update(
                start_datetime=start,
                end_datetime=end,
            )


# ---------------------------------------------------------------------------
# Validation warnings (soft — force=False)
# ---------------------------------------------------------------------------


class TestUpdateValidationWarnings:
    @freeze_time("2024-06-03 08:00:00")
    def test_single_space_conflict_raises_when_not_forced(self):
        space = SpaceFactory()
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        EventFactory(space=space, start_datetime=start, end_datetime=end)

        event = EventFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 6, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 6, 11, 0), UTC),
        )
        with pytest.raises(ValidationError):
            EventService(event).admin.update(
                force=False,
                start_datetime=start,
                end_datetime=end,
            )

    @freeze_time("2024-06-03 08:00:00")
    def test_bulk_series_conflict_raises_when_not_forced(self):
        space = SpaceFactory()
        template = RecurringTemplateFactory(
            space=space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 3, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 3, 11, 0), UTC),
        )
        e1 = EventFactory(
            space=space,
            service=template.service,
            recurrence_template=template,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
            recurrence_source_date=datetime.date(2024, 6, 10),
        )
        # Create an unrelated event that would conflict if series is moved to 14:00
        other_space = SpaceFactory()
        EventFactory(
            space=other_space,
            start_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 10, 0), UTC
            ),
            end_datetime=timezone.make_aware(
                datetime.datetime(2024, 6, 10, 11, 0), UTC
            ),
        )
        with pytest.raises(ValidationError):
            EventService(e1).admin.update(
                update_scope=EventUpdateScope.ALL_EVENTS_IN_SERIES,
                force=False,
                space=other_space,
            )
