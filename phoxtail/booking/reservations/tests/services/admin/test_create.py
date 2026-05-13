"""
Tests for the admin create operation.
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

from ...factories import ReservationFactory as ResFactory

pytestmark = pytest.mark.django_db


class TestAdminCreate:
    def _setup(self, **kw):
        location = LocationFactory()
        service = kw.pop("service", ServiceFactory())
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        user = kw.pop("user", UserFactory())
        subscription = kw.pop(
            "subscription",
            SubscriptionFactory(user=user, subscription_type=sub_type, is_paid=True, credits=10),
        )
        start = kw.pop("start_datetime", timezone.now() + datetime.timedelta(days=1))
        event = kw.pop(
            "event",
            EventFactory(
                service=service,
                space=space,
                start_datetime=start,
                end_datetime=start + datetime.timedelta(hours=1),
            ),
        )
        return user, event, subscription

    @freeze_time("2024-06-15 08:00:00")
    def test_creates_confirmed_reservation(self):
        user, event, sub = self._setup()
        r = ReservationService().admin.create(
            user_id=str(user.id),
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
        )
        assert r.status == ReservationStatus.CONFIRMED
        assert r.user == user
        assert r.event == event

    @freeze_time("2024-06-15 08:00:00")
    def test_creates_waitlisted_reservation(self):
        user, event, sub = self._setup()
        r = ReservationService().admin.create(
            user_id=str(user.id),
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
            status=ReservationStatus.WAITLISTED,
        )
        assert r.status == ReservationStatus.WAITLISTED

    @freeze_time("2024-06-15 08:00:00")
    def test_confirmed_deducts_credit(self):
        user, event, sub = self._setup()
        initial = sub.credits
        ReservationService().admin.create(
            user_id=str(user.id),
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
        )
        sub.refresh_from_db()
        assert sub.credits == initial - 1

    @freeze_time("2024-06-15 08:00:00")
    def test_waitlisted_does_not_deduct_credit(self):
        user, event, sub = self._setup()
        initial = sub.credits
        ReservationService().admin.create(
            user_id=str(user.id),
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
            status=ReservationStatus.WAITLISTED,
        )
        sub.refresh_from_db()
        assert sub.credits == initial

    @freeze_time("2024-06-15 08:00:00")
    def test_past_event_allowed(self):
        """Admins can create reservations for past events (e.g. record-keeping)."""
        user, event, sub = self._setup(start_datetime=timezone.now() - datetime.timedelta(hours=1))
        r = ReservationService().admin.create(
            user_id=str(user.id),
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
        )
        assert r.status == ReservationStatus.CONFIRMED

    @freeze_time("2024-06-15 08:00:00")
    def test_duplicate_confirmed_raises(self):
        user, event, sub = self._setup()
        ResFactory(user=user, event=event, status=ReservationStatus.CONFIRMED)
        with pytest.raises(ValidationError):
            ReservationService().admin.create(
                user_id=str(user.id),
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_cancelled_event_raises(self):
        user, event, sub = self._setup()
        event.status = EventStatus.CANCELLED
        event.save()
        with pytest.raises(ValidationError):
            ReservationService().admin.create(
                user_id=str(user.id),
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_full_event_raises_for_confirmed(self):
        user, event, sub = self._setup()
        event.capacity = 0
        event.save()
        with pytest.raises(ValidationError):
            ReservationService().admin.create(
                user_id=str(user.id),
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_overlapping_reservation_raises(self):
        user, event, sub = self._setup()
        # Create a reservation at the same time for a different event
        location2 = LocationFactory()
        space2 = SpaceFactory(location=location2)
        overlapping_event = EventFactory(
            service=event.service,
            space=space2,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
        )
        ResFactory(user=user, event=overlapping_event, status=ReservationStatus.CONFIRMED)
        with pytest.raises(ValidationError):
            ReservationService().admin.create(
                user_id=str(user.id),
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    # ------------------------------------------------------------------
    # Identifier contract tests
    # Protect the integer PK (user_id) / UUID (event_id, subscription_id)
    # boundary so accidental swaps fail loudly in tests, not in production.
    # ------------------------------------------------------------------

    @freeze_time("2024-06-15 08:00:00")
    def test_user_not_found_raises(self):
        _, event, sub = self._setup()
        with pytest.raises(ValidationError):
            ReservationService().admin.create(
                user_id="999999",
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_event_not_found_raises(self):
        user, _, sub = self._setup()
        with pytest.raises(ValidationError):
            ReservationService().admin.create(
                user_id=str(user.id),
                event_id="00000000-0000-0000-0000-000000000000",
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_subscription_not_found_raises(self):
        user, event, _ = self._setup()
        with pytest.raises(ValidationError):
            ReservationService().admin.create(
                user_id=str(user.id),
                event_id=str(event.uuid),
                subscription_id="00000000-0000-0000-0000-000000000000",
            )
