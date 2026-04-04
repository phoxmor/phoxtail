"""
Tests for ReservationService — the base service layer (getters, is_cancelled,
cancellation period checks).
"""

import datetime

import pytest
from freezegun import freeze_time

from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.services import ReservationService

from ..factories import ReservationFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# is_cancelled
# ---------------------------------------------------------------------------


class TestIsCancelled:
    def test_confirmed_returns_false(self):
        r = ReservationFactory(status=ReservationStatus.CONFIRMED)
        assert ReservationService(r).is_cancelled() is False

    def test_cancelled_returns_true(self):
        r = ReservationFactory(status=ReservationStatus.CANCELLED)
        assert ReservationService(r).is_cancelled() is True

    def test_waitlisted_returns_false(self):
        r = ReservationFactory(status=ReservationStatus.WAITLISTED)
        assert ReservationService(r).is_cancelled() is False

    def test_completed_returns_false(self):
        r = ReservationFactory(status=ReservationStatus.COMPLETED)
        assert ReservationService(r).is_cancelled() is False


# ---------------------------------------------------------------------------
# get_is_within_allowed_cancellation_period
# ---------------------------------------------------------------------------


class TestIsWithinAllowedCancellationPeriod:
    @freeze_time("2024-06-15 08:00:00")
    def test_well_before_event_returns_true(self):
        from django.utils import timezone

        from phoxtail.booking.events.tests.factories import EventFactory

        event = EventFactory(
            start_datetime=timezone.now() + datetime.timedelta(days=2),
            end_datetime=timezone.now() + datetime.timedelta(days=2, hours=1),
        )
        # service.cancellation_lockout_hours defaults to 1
        r = ReservationFactory(event=event)
        assert ReservationService(r).get_is_within_allowed_cancellation_period() is True

    @freeze_time("2024-06-15 08:00:00")
    def test_inside_lockout_returns_false(self):
        from django.utils import timezone

        from phoxtail.booking.events.tests.factories import EventFactory

        # Event starts in 30 minutes — inside 1-hour lockout
        event = EventFactory(
            start_datetime=timezone.now() + datetime.timedelta(minutes=30),
            end_datetime=timezone.now() + datetime.timedelta(minutes=90),
        )
        r = ReservationFactory(event=event)
        assert (
            ReservationService(r).get_is_within_allowed_cancellation_period() is False
        )


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------


class TestGetters:
    def test_get_user_username(self):
        r = ReservationFactory()
        assert ReservationService(r).get_user_username() == r.user.username

    def test_get_user_email(self):
        r = ReservationFactory()
        assert ReservationService(r).get_user_email() == r.user.email

    def test_get_user_full_name(self):
        r = ReservationFactory()
        assert ReservationService(r).get_user_full_name() == r.user.get_full_name()

    def test_get_event_service_name(self):
        r = ReservationFactory()
        assert ReservationService(r).get_event_service_name() == r.event.service.name

    def test_get_event_service_name_returns_string(self):
        r = ReservationFactory()
        assert isinstance(ReservationService(r).get_event_service_name(), str)
