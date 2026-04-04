"""
factory_boy factories for the reservations app test suite.

Reuses UserFactory, ServiceFactory from the subscriptions app
and EventFactory, SpaceFactory from the events app.
"""

import factory

from phoxtail.booking.events.tests.factories import EventFactory
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.reservations.models import Reservation
from phoxtail.booking.subscriptions.tests.factories import (
    SubscriptionFactory,
    UserFactory,
)


class ReservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Reservation

    user = factory.SubFactory(UserFactory)
    event = factory.SubFactory(EventFactory)
    subscription = factory.SubFactory(SubscriptionFactory)
    status = ReservationStatus.CONFIRMED
    notes = ""
