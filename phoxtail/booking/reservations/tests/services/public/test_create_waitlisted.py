"""
Tests for the public create_waitlisted operation.
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


class TestPublicCreateWaitlisted:
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
        event = kw.pop(
            "event",
            EventFactory(
                service=service,
                space=space,
                start_datetime=start,
                end_datetime=start + datetime.timedelta(hours=1),
                capacity=0,  # full by default for waitlisting
            ),
        )
        return user, event, subscription

    @freeze_time("2024-06-15 08:00:00")
    def test_creates_waitlisted_reservation(self):
        user, event, sub = self._setup()
        r = ReservationService().public.create_waitlisted(
            user=user,
            event_id=str(event.uuid),
            subscription_id=str(sub.uuid),
        )
        assert r.status == ReservationStatus.WAITLISTED

    @freeze_time("2024-06-15 08:00:00")
    def test_event_must_be_full(self):
        user, event, sub = self._setup()
        event.capacity = 100  # not full
        event.save()
        with pytest.raises(ValidationError):
            ReservationService().public.create_waitlisted(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_duplicate_confirmed_raises(self):
        user, event, sub = self._setup()
        ReservationFactory(user=user, event=event, status=ReservationStatus.CONFIRMED)
        with pytest.raises(ValidationError):
            ReservationService().public.create_waitlisted(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_duplicate_waitlisted_raises(self):
        user, event, sub = self._setup()
        ReservationFactory(user=user, event=event, status=ReservationStatus.WAITLISTED)
        with pytest.raises(ValidationError):
            ReservationService().public.create_waitlisted(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_duplicate_cancelled_raises(self):
        user, event, sub = self._setup()
        ReservationFactory(user=user, event=event, status=ReservationStatus.CANCELLED)
        with pytest.raises(ValidationError):
            ReservationService().public.create_waitlisted(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_duplicate_completed_raises(self):
        user, event, sub = self._setup()
        ReservationFactory(user=user, event=event, status=ReservationStatus.COMPLETED)
        with pytest.raises(ValidationError):
            ReservationService().public.create_waitlisted(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )

    @freeze_time("2024-06-15 08:00:00")
    def test_past_event_raises(self):
        user, event, sub = self._setup(start_datetime=timezone.now() - datetime.timedelta(hours=1))
        with pytest.raises(ValidationError):
            ReservationService().public.create_waitlisted(
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
            ReservationService().public.create_waitlisted(
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
            ReservationService().public.create_waitlisted(
                user=user,
                event_id=str(event.uuid),
                subscription_id=str(sub.uuid),
            )
