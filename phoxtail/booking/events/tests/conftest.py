import pytest

from phoxtail.booking.subscriptions.tests.factories import (
    LocationFactory,
    ServiceFactory,
    UserFactory,
)

from .factories import (
    EventFactory,
    RecurringTemplateFactory,
    SpaceFactory,
    StaffFactory,
)


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def other_user():
    return UserFactory()


@pytest.fixture
def location():
    return LocationFactory(timezone="UTC")


@pytest.fixture
def space(location):
    return SpaceFactory(location=location)


@pytest.fixture
def other_space(location):
    return SpaceFactory(location=location, name="Room B")


@pytest.fixture
def service():
    return ServiceFactory()


@pytest.fixture
def staff_member():
    return StaffFactory()


@pytest.fixture
def event(service, space):
    return EventFactory(service=service, space=space)


@pytest.fixture
def recurring_template(service, space):
    return RecurringTemplateFactory(service=service, space=space)
