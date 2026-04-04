"""
Tests for SubscriptionServiceAdminRenew (admin domain, renew operation).

A renewable subscription must be: ACTIVE status, paid, and either expired
or credits depleted. Each test covers one validation rule or one aspect of
the perform() side-effects.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from freezegun import freeze_time

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
        end_date=datetime.date(2020, 1, 1),  # clearly expired
    )


class TestAdminRenew:
    # ------------------------------------------------------------------
    # Happy path / state assertions
    # ------------------------------------------------------------------

    def test_archives_the_old_subscription(self, renewable_subscription):
        old_pk = renewable_subscription.pk
        SubscriptionService(renewable_subscription).admin.renew()
        assert Subscription.objects.get(pk=old_pk).status == SubscriptionStatus.ARCHIVED

    def test_returns_a_new_active_subscription(self, renewable_subscription):
        new_sub = SubscriptionService(renewable_subscription).admin.renew()
        assert new_sub.pk != renewable_subscription.pk
        assert new_sub.status == SubscriptionStatus.ACTIVE

    def test_new_subscription_has_fresh_credits(self, renewable_subscription):
        # Credits reset to the subscription type's allocation, not the old balance
        new_sub = SubscriptionService(renewable_subscription).admin.renew()
        new_sub.refresh_from_db()
        assert new_sub.credits == renewable_subscription.subscription_type.credits

    @freeze_time("2024-06-15")
    def test_new_subscription_start_date_is_today(self, renewable_subscription):
        new_sub = SubscriptionService(renewable_subscription).admin.renew()
        assert new_sub.start_date == datetime.date(2024, 6, 15)

    def test_both_subscriptions_are_persisted(self, renewable_subscription, user):
        count_before = Subscription.objects.filter(user=user).count()
        SubscriptionService(renewable_subscription).admin.renew()
        assert Subscription.objects.filter(user=user).count() == count_before + 1

    # ------------------------------------------------------------------
    # Validation failures
    # ------------------------------------------------------------------

    def test_raises_when_subscription_type_is_inactive(self, user):
        st = SubscriptionTypeFactory(is_active=False)
        sub = SubscriptionFactory(
            user=user,
            subscription_type=st,
            is_paid=True,
            credits=0,
        )
        with pytest.raises(ValidationError):
            SubscriptionService(sub).admin.renew()

    def test_raises_when_subscription_status_is_not_active(
        self, renewable_subscription
    ):
        renewable_subscription.status = SubscriptionStatus.CANCELLED
        renewable_subscription.save()
        with pytest.raises(ValidationError):
            SubscriptionService(renewable_subscription).admin.renew()

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
            SubscriptionService(sub).admin.renew()

    def test_raises_when_not_paid(self, renewable_subscription):
        renewable_subscription.is_paid = False
        renewable_subscription.save()
        with pytest.raises(ValidationError):
            SubscriptionService(renewable_subscription).admin.renew()
