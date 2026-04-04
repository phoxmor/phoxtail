"""
Tests for the admin cancel operation.
Covers: within/outside cancellation window, credit restoration,
waitlisted skips credit restore, and the bug fix verification.
"""

import datetime

import pytest
from django.utils import timezone
from freezegun import freeze_time

from phoxtail.booking.events.tests.factories import EventFactory, SpaceFactory
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.models import Reservation
from phoxtail.booking.reservations.services import ReservationService
from phoxtail.booking.subscriptions.tests.factories import (
    LocationFactory,
    ServiceFactory,
    SubscriptionFactory,
    SubscriptionTypeFactory,
    UserFactory,
)

from ...factories import ReservationFactory as ResFactory

pytestmark = pytest.mark.django_db


class TestAdminCancel:
    """Cancel operation tests."""

    def _setup(self, **overrides):
        """Helper to create a full reservation with accessible fields."""
        user = overrides.pop("user", UserFactory())
        location = LocationFactory()
        service = overrides.pop("service", ServiceFactory(cancellation_lockout_hours=1))
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        subscription = overrides.pop(
            "subscription",
            SubscriptionFactory(
                user=user, subscription_type=sub_type, is_paid=True, credits=10
            ),
        )

        start = overrides.pop(
            "start_datetime", timezone.now() + datetime.timedelta(days=1)
        )
        event = EventFactory(
            service=service,
            space=space,
            start_datetime=start,
            end_datetime=start + datetime.timedelta(hours=1),
        )

        status = overrides.pop("status", ReservationStatus.CONFIRMED)
        reservation = ResFactory(
            user=user,
            event=event,
            subscription=subscription,
            status=status,
        )
        return reservation, subscription

    @freeze_time("2024-06-15 08:00:00")
    def test_within_cancellation_period_deletes_reservation(self):
        """Early cancellation deletes the reservation entirely."""
        r, sub = self._setup(start_datetime=timezone.now() + datetime.timedelta(days=1))
        rid = r.id
        ReservationService(r).admin.cancel(user=r.user)
        assert not Reservation.objects.filter(id=rid).exists()

    @freeze_time("2024-06-15 08:00:00")
    def test_within_cancellation_period_restores_credit(self):
        """Early cancellation restores the subscription credit."""
        r, sub = self._setup(start_datetime=timezone.now() + datetime.timedelta(days=1))
        initial_credits = sub.credits
        # Simulate a credit was already used
        sub.credits = initial_credits - 1
        sub.save()

        ReservationService(r).admin.cancel(user=r.user)

        sub.refresh_from_db()
        assert sub.credits == initial_credits

    @freeze_time("2024-06-15 08:00:00")
    def test_outside_cancellation_period_marks_cancelled(self):
        """Late cancellation marks the reservation as CANCELLED."""
        r, sub = self._setup(
            start_datetime=timezone.now() + datetime.timedelta(minutes=30)
        )
        ReservationService(r).admin.cancel(user=r.user)

        r.refresh_from_db()
        assert r.status == ReservationStatus.CANCELLED

    @freeze_time("2024-06-15 08:00:00")
    def test_outside_cancellation_period_does_not_restore_credit(self):
        """Late cancellation does not restore credits."""
        r, sub = self._setup(
            start_datetime=timezone.now() + datetime.timedelta(minutes=30)
        )
        initial_credits = sub.credits
        ReservationService(r).admin.cancel(user=r.user)

        sub.refresh_from_db()
        assert sub.credits == initial_credits

    @freeze_time("2024-06-15 08:00:00")
    def test_waitlisted_early_cancel_does_not_restore_credit(self):
        """Bug fix: waitlisted reservations should NOT trigger credit restore."""
        r, sub = self._setup(
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            status=ReservationStatus.WAITLISTED,
        )
        initial_credits = sub.credits
        ReservationService(r).admin.cancel(user=r.user)

        sub.refresh_from_db()
        assert sub.credits == initial_credits

    @freeze_time("2024-06-15 08:00:00")
    def test_no_show_within_cancellation_period_deletes_and_restores_credit(self):
        """No-show early cancellation deletes and restores credit."""
        r, sub = self._setup(
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            status=ReservationStatus.NO_SHOW,
        )
        initial_credits = sub.credits
        sub.credits = initial_credits - 1
        sub.save()
        rid = r.id
        ReservationService(r).admin.cancel(user=r.user)
        assert not Reservation.objects.filter(id=rid).exists()
        sub.refresh_from_db()
        assert sub.credits == initial_credits

    @freeze_time("2024-06-15 08:00:00")
    def test_no_show_outside_cancellation_period_marks_cancelled(self):
        """No-show late cancellation marks as CANCELLED."""
        r, sub = self._setup(
            start_datetime=timezone.now() + datetime.timedelta(minutes=30),
            status=ReservationStatus.NO_SHOW,
        )
        ReservationService(r).admin.cancel(user=r.user)
        r.refresh_from_db()
        assert r.status == ReservationStatus.CANCELLED

    @freeze_time("2024-06-15 08:00:00")
    def test_waitlisted_early_cancel_still_deletes(self):
        """Waitlisted early cancellation still deletes the reservation."""
        r, sub = self._setup(
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            status=ReservationStatus.WAITLISTED,
        )
        rid = r.id
        ReservationService(r).admin.cancel(user=r.user)
        assert not Reservation.objects.filter(id=rid).exists()
