"""
Tests for the public create operation.
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


class TestPublicCreate:
    def _setup(self, **kw):
        user = kw.pop("user", UserFactory())
        location = LocationFactory()
        service = kw.pop("service", ServiceFactory())
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        subscription = kw.pop(
            "subscription",
            SubscriptionFactory(
                user=user, subscription_type=sub_type, is_paid=True, credits=10
            ),
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
        r = ReservationService().public.create(
            user=user,
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
        )
        assert r.status == ReservationStatus.CONFIRMED
        assert r.user == user
        assert r.event == event

    @freeze_time("2024-06-15 08:00:00")
    def test_deducts_credit(self):
        user, event, sub = self._setup()
        initial = sub.credits
        ReservationService().public.create(
            user=user,
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
        )
        sub.refresh_from_db()
        assert sub.credits == initial - 1

    @freeze_time("2024-06-15 08:00:00")
    def test_past_event_raises(self):
        user, event, sub = self._setup(
            start_datetime=timezone.now() - datetime.timedelta(hours=1)
        )
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_duplicate_raises(self):
        user, event, sub = self._setup()
        ReservationFactory(user=user, event=event, status=ReservationStatus.CONFIRMED)
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_cancelled_event_raises(self):
        user, event, sub = self._setup()
        event.status = EventStatus.CANCELLED
        event.save()
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_unpublished_event_raises(self):
        user, event, sub = self._setup()
        event.status = EventStatus.UNPUBLISHED
        event.save()
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_full_event_raises(self):
        user, event, sub = self._setup()
        event.capacity = 0
        event.save()
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_overlapping_reservation_raises(self):
        user, event, sub = self._setup()
        location2 = LocationFactory()
        space2 = SpaceFactory(location=location2)
        overlap_event = EventFactory(
            space=space2,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
        )
        ReservationFactory(
            user=user, event=overlap_event, status=ReservationStatus.CONFIRMED
        )
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_outside_subscription_period_raises(self):
        user, event, sub = self._setup()
        sub.end_date = (timezone.now() - datetime.timedelta(days=1)).date()
        sub.save()
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_invalid_subscription_raises(self):
        user, event, _ = self._setup()
        with pytest.raises(ValidationError):
            ReservationService().public.create(
                user=user,
                event_id=str(event.uuid),
                subscription_id="00000000-0000-0000-0000-000000000000",
            )
