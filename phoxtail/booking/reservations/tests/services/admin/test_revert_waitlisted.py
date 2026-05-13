"""
Tests for the admin revert_to_waitlisted operation.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from phoxtail.booking.events.tests.factories import EventFactory, SpaceFactory
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.services import ReservationService
from phoxtail.booking.subscriptions.tests.factories import (
    LocationFactory,
    ServiceFactory,
    SubscriptionFactory,
    SubscriptionTypeFactory,
    UserFactory,
)

from ...factories import ReservationFactory

pytestmark = pytest.mark.django_db


class TestAdminRevertWaitlisted:
    def _make(self, status=ReservationStatus.CONFIRMED):
        user = UserFactory()
        location = LocationFactory()
        service = ServiceFactory()
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        subscription = SubscriptionFactory(user=user, subscription_type=sub_type, is_paid=True, credits=10)
        event = EventFactory(
            service=service,
            space=space,
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            end_datetime=timezone.now() + datetime.timedelta(days=1, hours=1),
        )
        r = ReservationFactory(user=user, event=event, subscription=subscription, status=status)
        return r, subscription

    def test_confirmed_becomes_waitlisted(self):
        r, sub = self._make(ReservationStatus.CONFIRMED)
        result = ReservationService(r).admin.revert_to_waitlisted()
        result.refresh_from_db()
        assert result.status == ReservationStatus.WAITLISTED

    def test_completed_becomes_waitlisted(self):
        r, sub = self._make(ReservationStatus.COMPLETED)
        result = ReservationService(r).admin.revert_to_waitlisted()
        result.refresh_from_db()
        assert result.status == ReservationStatus.WAITLISTED

    def test_restores_credit(self):
        r, sub = self._make(ReservationStatus.CONFIRMED)
        initial = sub.credits
        sub.credits = initial - 1
        sub.save()
        ReservationService(r).admin.revert_to_waitlisted()
        sub.refresh_from_db()
        assert sub.credits == initial

    def test_waitlisted_raises(self):
        r, _ = self._make(ReservationStatus.WAITLISTED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.revert_to_waitlisted()

    def test_no_show_becomes_waitlisted_and_restores_credit(self):
        r, sub = self._make(ReservationStatus.NO_SHOW)
        initial = sub.credits
        sub.credits = initial - 1
        sub.save()
        result = ReservationService(r).admin.revert_to_waitlisted()
        result.refresh_from_db()
        assert result.status == ReservationStatus.WAITLISTED
        sub.refresh_from_db()
        assert sub.credits == initial

    def test_cancelled_raises(self):
        r, _ = self._make(ReservationStatus.CANCELLED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.revert_to_waitlisted()
