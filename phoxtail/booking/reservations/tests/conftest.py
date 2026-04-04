import datetime

import pytest
from django.utils import timezone

from phoxtail.booking.events.tests.factories import EventFactory, SpaceFactory
from phoxtail.booking.subscriptions.tests.factories import (
    LocationFactory,
    ServiceFactory,
    SubscriptionFactory,
    SubscriptionTypeFactory,
    UserFactory,
)

from .factories import ReservationFactory


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def other_user():
    return UserFactory()


@pytest.fixture
def location():
    return LocationFactory()


@pytest.fixture
def service():
    return ServiceFactory()


@pytest.fixture
def space(location):
    return SpaceFactory(location=location)


@pytest.fixture
def subscription_type(location):
    return SubscriptionTypeFactory(location=location)


@pytest.fixture
def subscription(user, subscription_type):
    return SubscriptionFactory(
        user=user,
        subscription_type=subscription_type,
        is_paid=True,
        credits=10,
    )


@pytest.fixture
def future_event(service, space):
    """An event starting tomorrow."""
    tomorrow = timezone.now() + datetime.timedelta(days=1)
    return EventFactory(
        service=service,
        space=space,
        start_datetime=tomorrow,
        end_datetime=tomorrow + datetime.timedelta(hours=1),
    )


@pytest.fixture
def reservation(user, future_event, subscription):
    return ReservationFactory(
        user=user,
        event=future_event,
        subscription=subscription,
    )
