"""
Tests for the admin confirm operation.
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


class TestAdminConfirmWaitlisted:
    """Waitlisted → Confirmed transition."""

    def _make_waitlisted(self, **kw):
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
            ),
        )
        r = ReservationFactory(
            user=user,
            event=event,
            subscription=subscription,
            status=ReservationStatus.WAITLISTED,
        )
        return r, subscription

    @freeze_time("2024-06-15 08:00:00")
    def test_waitlisted_becomes_confirmed(self):
        r, sub = self._make_waitlisted()
        result = ReservationService(r).admin.confirm(subscription_id=str(sub.uuid))
        result.refresh_from_db()
        assert result.status == ReservationStatus.CONFIRMED

    @freeze_time("2024-06-15 08:00:00")
    def test_waitlisted_confirm_uses_credit(self):
        r, sub = self._make_waitlisted()
        initial = sub.credits
        ReservationService(r).admin.confirm(subscription_id=str(sub.uuid))
        sub.refresh_from_db()
        assert sub.credits == initial - 1

    @freeze_time("2024-06-15 08:00:00")
    def test_waitlisted_requires_subscription_id(self):
        r, _ = self._make_waitlisted()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.confirm()

    @freeze_time("2024-06-15 08:00:00")
    def test_past_event_raises(self):
        r, sub = self._make_waitlisted(
            start_datetime=timezone.now() - datetime.timedelta(hours=1),
        )
        with pytest.raises(ValidationError):
            ReservationService(r).admin.confirm(subscription_id=str(sub.uuid))

    @freeze_time("2024-06-15 08:00:00")
    def test_cancelled_event_raises(self):
        r, sub = self._make_waitlisted()
        r.event.status = EventStatus.CANCELLED
        r.event.save()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.confirm(subscription_id=str(sub.uuid))

    @freeze_time("2024-06-15 08:00:00")
    def test_full_event_raises(self):
        r, sub = self._make_waitlisted()
        r.event.capacity = 0
        r.event.save()
        with pytest.raises(ValidationError):
            ReservationService(r).admin.confirm(subscription_id=str(sub.uuid))


class TestAdminConfirmCancelled:
    """Cancelled → Confirmed transition (no credit consumed)."""

    @freeze_time("2024-06-15 08:00:00")
    def test_cancelled_becomes_confirmed(self):
        location = LocationFactory()
        service = ServiceFactory()
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        user = UserFactory()
        subscription = SubscriptionFactory(user=user, subscription_type=sub_type, is_paid=True, credits=10)
        event = EventFactory(
            service=service,
            space=space,
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            end_datetime=timezone.now() + datetime.timedelta(days=1, hours=1),
        )
        r = ReservationFactory(
            user=user,
            event=event,
            subscription=subscription,
            status=ReservationStatus.CANCELLED,
        )
        result = ReservationService(r).admin.confirm()
        result.refresh_from_db()
        assert result.status == ReservationStatus.CONFIRMED

    @freeze_time("2024-06-15 08:00:00")
    def test_cancelled_confirm_does_not_use_credit(self):
        location = LocationFactory()
        service = ServiceFactory()
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        user = UserFactory()
        subscription = SubscriptionFactory(user=user, subscription_type=sub_type, is_paid=True, credits=10)
        event = EventFactory(
            service=service,
            space=space,
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            end_datetime=timezone.now() + datetime.timedelta(days=1, hours=1),
        )
        r = ReservationFactory(
            user=user,
            event=event,
            subscription=subscription,
            status=ReservationStatus.CANCELLED,
        )
        initial = subscription.credits
        ReservationService(r).admin.confirm()
        subscription.refresh_from_db()
        assert subscription.credits == initial


class TestAdminConfirmNoShow:
    """No-show → Confirmed transition (no credit consumed)."""

    @freeze_time("2024-06-15 08:00:00")
    def test_no_show_becomes_confirmed(self):
        location = LocationFactory()
        service = ServiceFactory()
        space = SpaceFactory(location=location)
        sub_type = SubscriptionTypeFactory(location=location)
        user = UserFactory()
        subscription = SubscriptionFactory(user=user, subscription_type=sub_type, is_paid=True, credits=10)
        event = EventFactory(
            service=service,
            space=space,
            start_datetime=timezone.now() + datetime.timedelta(days=1),
            end_datetime=timezone.now() + datetime.timedelta(days=1, hours=1),
        )
        r = ReservationFactory(
            user=user,
            event=event,
            subscription=subscription,
            status=ReservationStatus.NO_SHOW,
        )
        result = ReservationService(r).admin.confirm()
        result.refresh_from_db()
        assert result.status == ReservationStatus.CONFIRMED


class TestAdminConfirmInvalidStatus:
    def test_confirmed_raises(self):
        r = ReservationFactory(status=ReservationStatus.CONFIRMED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.confirm()

    def test_completed_raises(self):
        r = ReservationFactory(status=ReservationStatus.COMPLETED)
        with pytest.raises(ValidationError):
            ReservationService(r).admin.confirm()
