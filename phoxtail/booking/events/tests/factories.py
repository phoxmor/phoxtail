"""
factory_boy factories for the events app test suite.

Reuses UserFactory, LocationFactory, ServiceFactory from the subscriptions app.
"""

import datetime

import factory
from django.utils import timezone

from phoxtail.booking.core.models import Space, Staff
from phoxtail.booking.events.constants import EventStatus, RecurrenceFrequency
from phoxtail.booking.events.models import Event
from phoxtail.booking.subscriptions.tests.factories import (
    LocationFactory,
    ServiceFactory,
    UserFactory,
)


class SpaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Space

    location = factory.SubFactory(LocationFactory)
    name = factory.Sequence(lambda n: f"Room {n}")
    capacity = 12
    is_active = True


class StaffFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Staff

    user = factory.SubFactory(UserFactory)
    bio = ""


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    service = factory.SubFactory(ServiceFactory)
    start_datetime = factory.LazyFunction(lambda: timezone.now().replace(hour=10, minute=0, second=0, microsecond=0))
    end_datetime = factory.LazyFunction(lambda: timezone.now().replace(hour=11, minute=0, second=0, microsecond=0))
    space = factory.SubFactory(SpaceFactory)
    capacity = 12
    status = EventStatus.CONFIRMED
    is_recurrence_template = False
    recurrence_template = None
    recurrence_source_date = None


class RecurringTemplateFactory(EventFactory):
    is_recurrence_template = True
    recurrence_freq = RecurrenceFrequency.WEEKLY
    recurrence_interval = 1
    recurrence_byweekday = [0]  # Monday
    recurrence_until = factory.LazyAttribute(lambda obj: obj.start_datetime + datetime.timedelta(days=90))
