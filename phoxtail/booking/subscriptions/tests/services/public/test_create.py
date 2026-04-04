"""
Tests for SubscriptionServicePublicCreate (public domain, create operation).

The public path adds two extra validation rules on top of the admin path:
the subscription type must be both active AND publicly visible.
Error messages are user-facing but we only assert that ValidationError
is raised, not the specific wording (message text is implementation detail).
"""

import pytest
from django.core.exceptions import ValidationError

from phoxtail.booking.subscriptions.constants import SubscriptionStatus
from phoxtail.booking.subscriptions.services import SubscriptionService

from ...factories import (
    SubscriptionFactory,
    SubscriptionTypeCreditAllocationFactory,
    SubscriptionTypeFactory,
)

pytestmark = pytest.mark.django_db


class TestPublicCreate:
    # ------------------------------------------------------------------
    # Happy path / state assertions
    # ------------------------------------------------------------------

    def test_creates_subscription_with_correct_user_and_type(
        self, user, subscription_type
    ):
        sub = SubscriptionService().public.create(user, subscription_type)
        assert sub.user == user
        assert sub.subscription_type == subscription_type
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_initializes_per_service_credit_balances(self, user, service):
        st = SubscriptionTypeFactory(credits=5)
        SubscriptionTypeCreditAllocationFactory(
            subscription_type=st, service=service, credits=4
        )
        sub = SubscriptionService().public.create(user, st)
        balance = sub.credit_balances.get(service=service)
        assert balance.credits == 4

    # ------------------------------------------------------------------
    # Validation failures — shared with admin
    # ------------------------------------------------------------------

    def test_raises_for_inactive_type(self, user):
        st = SubscriptionTypeFactory(is_active=False, is_public=True)
        with pytest.raises(ValidationError):
            SubscriptionService().public.create(user, st)

    def test_raises_when_user_has_unpaid_subscription(self, user, subscription_type):
        SubscriptionFactory(user=user, is_paid=False)
        with pytest.raises(ValidationError):
            SubscriptionService().public.create(user, subscription_type)

    def test_raises_for_duplicate_active_subscription_of_same_type(
        self, user, subscription_type
    ):
        SubscriptionFactory(
            user=user,
            subscription_type=subscription_type,
            status=SubscriptionStatus.ACTIVE,
            is_paid=True,
        )
        with pytest.raises(ValidationError):
            SubscriptionService().public.create(user, subscription_type)

    # ------------------------------------------------------------------
    # Validation failures — public-only rules
    # ------------------------------------------------------------------

    def test_raises_for_non_public_type(self, user):
        st = SubscriptionTypeFactory(is_active=True, is_public=False)
        with pytest.raises(ValidationError):
            SubscriptionService().public.create(user, st)

    # ------------------------------------------------------------------
    # Boundary: archived subscriptions are not active duplicates
    # ------------------------------------------------------------------

    def test_archived_subscription_does_not_block_creation(
        self, user, subscription_type
    ):
        SubscriptionFactory(
            user=user,
            subscription_type=subscription_type,
            status=SubscriptionStatus.ARCHIVED,
            is_paid=True,
        )
        sub = SubscriptionService().public.create(user, subscription_type)
        assert sub.pk is not None
