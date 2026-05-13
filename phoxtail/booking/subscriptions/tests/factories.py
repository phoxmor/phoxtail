"""
factory_boy factories for the subscriptions app test suite.

Shared factories (UserFactory, LocationFactory, ServiceFactory) live here for
now. As other booking apps grow their own test suites, extract them into a
common booking/tests/factories.py and import from there.
"""

import datetime

import factory
from django.contrib.auth import get_user_model

from phoxtail.booking.core.models import Location
from phoxtail.booking.services.models import Service
from phoxtail.booking.subscriptions.constants import SubscriptionStatus
from phoxtail.booking.subscriptions.models import (
    Subscription,
    SubscriptionCreditBalance,
    SubscriptionType,
    SubscriptionTypeCreditAllocation,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location

    name = factory.Sequence(lambda n: f"Location {n}")
    street_address_line1 = factory.Faker("street_address")
    city = factory.Faker("city")
    country = "US"
    # E.164 format required by PhoneNumberField
    phone_number = factory.Sequence(lambda n: f"+1212555{n % 10000:04d}")
    email = factory.Sequence(lambda n: f"location{n}@example.com")
    timezone = "UTC"


class ServiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Service

    name = factory.Sequence(lambda n: f"Service {n}")
    is_active = True


class SubscriptionTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubscriptionType

    location = factory.SubFactory(LocationFactory)
    name = factory.Sequence(lambda n: f"Subscription Type {n}")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True, min_value=1)
    is_active = True
    is_public = True
    duration = 30  # days
    credits = 10
    unpaid_reservation_limit = 0


class SubscriptionTypeCreditAllocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubscriptionTypeCreditAllocation

    subscription_type = factory.SubFactory(SubscriptionTypeFactory)
    service = factory.SubFactory(ServiceFactory)
    credits = 5


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subscription

    user = factory.SubFactory(UserFactory)
    subscription_type = factory.SubFactory(SubscriptionTypeFactory)
    start_date = factory.LazyFunction(datetime.date.today)
    end_date = None  # unlimited by default
    status = SubscriptionStatus.ACTIVE
    is_paid = True
    credits = 10
    unpaid_reservation_limit = 0


class SubscriptionCreditBalanceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubscriptionCreditBalance

    subscription = factory.SubFactory(SubscriptionFactory)
    service = factory.SubFactory(ServiceFactory)
    credits = 5
