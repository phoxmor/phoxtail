"""
Tests for SubscriptionServiceAdminCreate (admin domain, create operation).

Each test exercises a single concern: either a validation rule fires correctly,
or the happy-path perform() produces the expected database state.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from freezegun import freeze_time

from phoxtail.booking.subscriptions.constants import SubscriptionStatus
from phoxtail.booking.subscriptions.models import Subscription
from phoxtail.booking.subscriptions.services import SubscriptionService

from ...factories import (
    SubscriptionFactory,
    SubscriptionTypeCreditAllocationFactory,
    SubscriptionTypeFactory,
)

pytestmark = pytest.mark.django_db


class TestAdminCreate:
    # ------------------------------------------------------------------
    # Happy path / state assertions
    # ------------------------------------------------------------------

    def test_creates_subscription_with_correct_user_and_type(self, user, subscription_type):
        sub = SubscriptionService().admin.create(user, subscription_type)
        assert sub.user == user
        assert sub.subscription_type == subscription_type
        assert sub.status == SubscriptionStatus.ACTIVE

    @freeze_time("2024-06-15")
    def test_sets_end_date_from_type_duration(self, user):
        st = SubscriptionTypeFactory(duration=30)
        sub = SubscriptionService().admin.create(user, st)
        assert sub.end_date == datetime.date(2024, 7, 15)

    def test_no_end_date_when_duration_is_none(self, user):
        st = SubscriptionTypeFactory(duration=None)
        sub = SubscriptionService().admin.create(user, st)
        assert sub.end_date is None

    def test_initializes_shared_credits_from_type(self, user):
        st = SubscriptionTypeFactory(credits=20)
        sub = SubscriptionService().admin.create(user, st)
        sub.refresh_from_db()
        assert sub.credits == 20

    def test_initializes_per_service_credit_balances(self, user, service):
        st = SubscriptionTypeFactory(credits=5)
        SubscriptionTypeCreditAllocationFactory(subscription_type=st, service=service, credits=7)
        sub = SubscriptionService().admin.create(user, st)
        balance = sub.credit_balances.get(service=service)
        assert balance.credits == 7

    @freeze_time("2024-06-15")
    def test_defaults_start_date_to_today_in_location_timezone(self, user):
        st = SubscriptionTypeFactory(duration=None)
        sub = SubscriptionService().admin.create(user, st)
        assert sub.start_date == datetime.date(2024, 6, 15)

    def test_accepts_explicit_start_date(self, user, subscription_type):
        custom_date = datetime.date(2025, 3, 1)
        sub = SubscriptionService().admin.create(user, subscription_type, start_date=custom_date)
        assert sub.start_date == custom_date

    def test_persists_subscription_to_database(self, user, subscription_type):
        count_before = Subscription.objects.filter(user=user).count()
        SubscriptionService().admin.create(user, subscription_type)
        assert Subscription.objects.filter(user=user).count() == count_before + 1

    # ------------------------------------------------------------------
    # Validation failures
    # ------------------------------------------------------------------

    def test_raises_for_inactive_subscription_type(self, user):
        st = SubscriptionTypeFactory(is_active=False)
        with pytest.raises(ValidationError):
            SubscriptionService().admin.create(user, st)

    def test_raises_when_user_has_unpaid_subscription(self, user, subscription_type):
        SubscriptionFactory(user=user, is_paid=False)
        with pytest.raises(ValidationError):
            SubscriptionService().admin.create(user, subscription_type)

    def test_raises_for_duplicate_active_subscription_of_same_type(self, user, subscription_type):
        SubscriptionFactory(
            user=user,
            subscription_type=subscription_type,
            status=SubscriptionStatus.ACTIVE,
            is_paid=True,
        )
        with pytest.raises(ValidationError):
            SubscriptionService().admin.create(user, subscription_type)

    def test_archived_subscription_does_not_block_creation(self, user, subscription_type):
        # Historical (archived) subscriptions are not considered active duplicates
        SubscriptionFactory(
            user=user,
            subscription_type=subscription_type,
            status=SubscriptionStatus.ARCHIVED,
            is_paid=True,
        )
        sub = SubscriptionService().admin.create(user, subscription_type)
        assert sub.pk is not None
