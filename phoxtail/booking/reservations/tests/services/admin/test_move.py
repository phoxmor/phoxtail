"""
Tests for the admin move operation.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from phoxtail.booking.events.constants import EventStatus
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


class TestAdminMove:
    def _setup(self, **kw):
        user = kw.pop("user", UserFactory())
        location = LocationFactory()
        service = kw.pop("service", ServiceFactory())
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        subscription = kw.pop(
            "subscription",
            SubscriptionFactory(user=user, subscription_type=sub_type, is_paid=True, credits=10),
        )
        start = kw.pop("start_datetime", timezone.now() + datetime.timedelta(days=1))
        event = EventFactory(
            service=service,
            space=space,
            start_datetime=start,
            end_datetime=start + datetime.timedelta(hours=1),
        )
        r = ReservationFactory(
            user=user,
            event=event,
            subscription=subscription,
            status=ReservationStatus.CONFIRMED,
        )

        # Target event (different time, same service by default)
        target_start = start + datetime.timedelta(days=1)
        target_service = kw.pop("target_service", service)
        target_event = kw.pop(
            "target_event",
            EventFactory(
                service=target_service,
                space=space,
                start_datetime=target_start,
                end_datetime=target_start + datetime.timedelta(hours=1),
            ),
        )
        return r, target_event, subscription

    @freeze_time("2024-06-15 08:00:00")
    def test_event_changes_to_target(self):
        r, target, _ = self._setup()
        result = ReservationService(r).admin.move(target_event_id=str(target.uuid))
        result.refresh_from_db()
        assert result.event.id == target.id

    @freeze_time("2024-06-15 08:00:00")
    def test_same_service_no_credit_swap(self):
        r, target, sub = self._setup()
        initial = sub.credits
        ReservationService(r).admin.move(target_event_id=str(target.uuid))
        sub.refresh_from_db()
        assert sub.credits == initial

    @freeze_time("2024-06-15 08:00:00")
    def test_cross_service_swaps_credits(self):
        service2 = ServiceFactory()
        r, target, sub = self._setup(target_service=service2)
        # Simulate that a credit was already used for the original event
        sub.credits = sub.credits - 1
        sub.save()
        initial = sub.credits
        ReservationService(r).admin.move(target_event_id=str(target.uuid))
        sub.refresh_from_db()
        # restore (+1) + use (-1) = net zero change for shared credits
        assert sub.credits == initial

    @freeze_time("2024-06-15 08:00:00")
    def test_same_event_raises(self):
        r, _, _ = self._setup()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.move(target_event_id=str(r.event.uuid))

    @freeze_time("2024-06-15 08:00:00")
    def test_cancelled_target_raises(self):
        r, target, _ = self._setup()
        target.status = EventStatus.CANCELLED
        target.save()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.move(target_event_id=str(target.uuid))

    @freeze_time("2024-06-15 08:00:00")
    def test_duplicate_at_target_raises(self):
        r, target, _ = self._setup()
        ReservationFactory(user=r.user, event=target, status=ReservationStatus.CONFIRMED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.move(target_event_id=str(target.uuid))

    @freeze_time("2024-06-15 08:00:00")
    def test_no_show_duplicate_at_target_raises(self):
        r, target, _ = self._setup()
        ReservationFactory(user=r.user, event=target, status=ReservationStatus.NO_SHOW)
        with pytest.raises(ValidationError, match="no-show"):
            ReservationService(r).admin.move(target_event_id=str(target.uuid))

    @freeze_time("2024-06-15 08:00:00")
    def test_full_target_raises(self):
        r, target, _ = self._setup()
        target.capacity = 0
        target.save()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.move(target_event_id=str(target.uuid))

    @freeze_time("2024-06-15 08:00:00")
    def test_past_target_allowed(self):
        """Admins can move a reservation to a past event (e.g. record-keeping)."""
        r, _, _ = self._setup()
        location2 = LocationFactory()
        space2 = SpaceFactory(location=location2)
        past_event = EventFactory(
            space=space2,
            start_datetime=timezone.now() - datetime.timedelta(hours=1),
            end_datetime=timezone.now() - datetime.timedelta(minutes=1),
        )
        result = ReservationService(r).admin.move(target_event_id=str(past_event.uuid))
        result.refresh_from_db()
        assert result.event.id == past_event.id

    @freeze_time("2024-06-15 08:00:00")
    def test_overlapping_reservation_raises(self):
        r, target, _ = self._setup()
        # Create another reservation for the user at the same time as target
        location2 = LocationFactory()
        space2 = SpaceFactory(location=location2)
        overlap_event = EventFactory(
            space=space2,
            start_datetime=target.start_datetime,
            end_datetime=target.end_datetime,
        )
        ReservationFactory(user=r.user, event=overlap_event, status=ReservationStatus.CONFIRMED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.move(target_event_id=str(target.uuid))
