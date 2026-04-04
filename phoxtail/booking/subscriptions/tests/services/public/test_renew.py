"""
Tests for SubscriptionServicePublicRenew (public domain, renew operation).

The public path adds one extra validation rule on top of the admin path:
the subscription type must still be publicly visible. All other rules match
the admin renew contract.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError

from phoxtail.booking.subscriptions.constants import SubscriptionStatus
from phoxtail.booking.subscriptions.models import Subscription
from phoxtail.booking.subscriptions.services import SubscriptionService

from ...factories import SubscriptionFactory, SubscriptionTypeFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def renewable_subscription(user, subscription_type):
    """A subscription in a state that satisfies all renewal pre-conditions."""
    return SubscriptionFactory(
        user=user,
        subscription_type=subscription_type,
        is_paid=True,
        credits=0,
        end_date=datetime.date(2020, 1, 1),
    )


class TestPublicRenew:
    # ------------------------------------------------------------------
    # Happy path / state assertions
    # ------------------------------------------------------------------

    def test_archives_old_and_returns_new_active_subscription(
        self, renewable_subscription
    ):
        old_pk = renewable_subscription.pk
        new_sub = SubscriptionService(renewable_subscription).public.renew()
        assert Subscription.objects.get(pk=old_pk).status == SubscriptionStatus.ARCHIVED
        assert new_sub.status == SubscriptionStatus.ACTIVE
        assert new_sub.pk != old_pk

    # ------------------------------------------------------------------
    # Validation failures — shared with admin
    # ------------------------------------------------------------------

    def test_raises_when_subscription_type_is_inactive(self, user):
        st = SubscriptionTypeFactory(is_active=False, is_public=True)
        sub = SubscriptionFactory(
            user=user,
            subscription_type=st,
            is_paid=True,
            credits=0,
            end_date=datetime.date(2020, 1, 1),
        )
        with pytest.raises(ValidationError):
            SubscriptionService(sub).public.renew()

    def test_raises_when_subscription_status_is_not_active(
        self, renewable_subscription
    ):
        renewable_subscription.status = SubscriptionStatus.SUSPENDED
        renewable_subscription.save()
        with pytest.raises(ValidationError):
            SubscriptionService(renewable_subscription).public.renew()

    def test_raises_when_still_active_with_remaining_credits(
        self, user, subscription_type
    ):
        sub = SubscriptionFactory(
            user=user,
            subscription_type=subscription_type,
            is_paid=True,
            credits=5,
            end_date=None,
        )
        with pytest.raises(ValidationError):
            SubscriptionService(sub).public.renew()

    def test_raises_when_not_paid(self, renewable_subscription):
        renewable_subscription.is_paid = False
        renewable_subscription.save()
        with pytest.raises(ValidationError):
            SubscriptionService(renewable_subscription).public.renew()

    # ------------------------------------------------------------------
    # Validation failures — public-only rules
    # ------------------------------------------------------------------

    def test_raises_for_non_public_type(self, user):
        st = SubscriptionTypeFactory(is_active=True, is_public=False)
        sub = SubscriptionFactory(
            user=user,
            subscription_type=st,
            is_paid=True,
            credits=0,
            end_date=datetime.date(2020, 1, 1),
        )
        with pytest.raises(ValidationError):
            SubscriptionService(sub).public.renew()
