"""
Tests for EventServiceAdminUpdateTemplate — updating recurrence template events.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from phoxtail.booking.events.services import EventService
from phoxtail.booking.subscriptions.tests.factories import ServiceFactory

from ...factories import RecurringTemplateFactory, StaffFactory

UTC = datetime.UTC

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestUpdateTemplateHappyPath:
    @freeze_time("2024-06-03 08:00:00")
    def test_updates_template_fields(self):
        template = RecurringTemplateFactory()
        new_service = ServiceFactory()
        updated = EventService(template).admin.update_template(
            service=new_service,
            capacity=50,
        )
        updated.refresh_from_db()
        assert updated.service == new_service
        assert updated.capacity == 50

    @freeze_time("2024-06-03 08:00:00")
    def test_updates_staff(self):
        template = RecurringTemplateFactory()
        staff = StaffFactory()
        updated = EventService(template).admin.update_template(
            staff=[staff],
        )
        assert staff in updated.staff.all()

    @freeze_time("2024-06-03 08:00:00")
    def test_returns_the_template(self):
        template = RecurringTemplateFactory()
        result = EventService(template).admin.update_template(
            capacity=30,
        )
        assert result.pk == template.pk


# ---------------------------------------------------------------------------
# Validation errors (hard)
# ---------------------------------------------------------------------------


class TestUpdateTemplateValidationErrors:
    def test_end_before_start_raises(self):
        template = RecurringTemplateFactory()
        start = timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC)
        end = timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC)
        with pytest.raises(ValidationError):
            EventService(template).admin.update_template(
                start_datetime=start,
                end_datetime=end,
            )

    def test_recurrence_until_before_start_raises(self):
        template = RecurringTemplateFactory(
            start_datetime=timezone.make_aware(datetime.datetime(2024, 6, 5, 10, 0), UTC),
            end_datetime=timezone.make_aware(datetime.datetime(2024, 6, 5, 11, 0), UTC),
        )
        with pytest.raises(ValidationError):
            EventService(template).admin.update_template(
                recurrence_until=timezone.make_aware(datetime.datetime(2024, 6, 4, 10, 0), UTC),
            )
