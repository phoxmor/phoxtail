"""
Tests for the admin mark_no_show operation.
"""

import pytest
from django.core.exceptions import ValidationError

from phoxtail.booking.events.constants import EventStatus
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.services import ReservationService

from ...factories import ReservationFactory

pytestmark = pytest.mark.django_db


class TestAdminMarkNoShow:
    def test_confirmed_becomes_no_show(self):
        r = ReservationFactory(status=ReservationStatus.CONFIRMED)
        result = ReservationService(r).admin.mark_no_show()
        result.refresh_from_db()
        assert result.status == ReservationStatus.NO_SHOW

    def test_completed_becomes_no_show(self):
        r = ReservationFactory(status=ReservationStatus.COMPLETED)
        result = ReservationService(r).admin.mark_no_show()
        result.refresh_from_db()
        assert result.status == ReservationStatus.NO_SHOW

    def test_waitlisted_raises(self):
        r = ReservationFactory(status=ReservationStatus.WAITLISTED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.mark_no_show()

    def test_cancelled_raises(self):
        r = ReservationFactory(status=ReservationStatus.CANCELLED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.mark_no_show()

    def test_already_no_show_raises(self):
        r = ReservationFactory(status=ReservationStatus.NO_SHOW)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.mark_no_show()

    def test_cancelled_event_raises(self):
        r = ReservationFactory(status=ReservationStatus.CONFIRMED)
        r.event.status = EventStatus.CANCELLED
        r.event.save()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.mark_no_show()
