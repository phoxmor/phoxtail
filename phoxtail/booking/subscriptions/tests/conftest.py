import pytest

from .factories import (
    LocationFactory,
    ServiceFactory,
    SubscriptionFactory,
    SubscriptionTypeFactory,
    UserFactory,
)


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
