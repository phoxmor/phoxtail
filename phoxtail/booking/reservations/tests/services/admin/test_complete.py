"""
Tests for the admin complete operation.
"""

import pytest
from django.core.exceptions import ValidationError

from phoxtail.booking.events.constants import EventStatus
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.services import ReservationService

from ...factories import ReservationFactory

pytestmark = pytest.mark.django_db


class TestAdminComplete:
    def test_confirmed_reservation_becomes_completed(self):
        r = ReservationFactory(status=ReservationStatus.CONFIRMED)
        result = ReservationService(r).admin.complete()
        result.refresh_from_db()
        assert result.status == ReservationStatus.COMPLETED

    def test_non_confirmed_raises(self):
        r = ReservationFactory(status=ReservationStatus.WAITLISTED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.complete()

    def test_cancelled_status_raises(self):
        r = ReservationFactory(status=ReservationStatus.CANCELLED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.complete()

    def test_no_show_becomes_completed(self):
        r = ReservationFactory(status=ReservationStatus.NO_SHOW)
        result = ReservationService(r).admin.complete()
        result.refresh_from_db()
        assert result.status == ReservationStatus.COMPLETED

    def test_cancelled_event_raises(self):
        r = ReservationFactory(status=ReservationStatus.CONFIRMED)
        r.event.status = EventStatus.CANCELLED
        r.event.save()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.complete()
