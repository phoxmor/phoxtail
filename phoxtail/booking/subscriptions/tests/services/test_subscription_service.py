"""
Tests for SubscriptionService — the core business logic layer.

These tests verify the service in isolation by constructing model instances
directly via factories (bypassing the creation service), which gives full
control over the exact state under test.
"""

import datetime

import pytest
from freezegun import freeze_time

from phoxtail.booking.subscriptions.constants import SubscriptionStatus
from phoxtail.booking.subscriptions.services import SubscriptionService

from ..factories import (
    ServiceFactory,
    SubscriptionCreditBalanceFactory,
    SubscriptionFactory,
    SubscriptionTypeCreditAllocationFactory,
    SubscriptionTypeFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# is_expired
# ---------------------------------------------------------------------------


class TestIsExpired:
    def test_no_end_date_returns_false(self):
        sub = SubscriptionFactory(end_date=None)
        assert SubscriptionService(sub).is_expired() is False

    @freeze_time("2024-06-15")
    def test_past_end_date_returns_true(self):
        sub = SubscriptionFactory(end_date=datetime.date(2024, 6, 14))
        assert SubscriptionService(sub).is_expired() is True

    @freeze_time("2024-06-15")
    def test_same_day_end_date_not_yet_expired(self):
        # Expires at end of day — still valid today
        sub = SubscriptionFactory(end_date=datetime.date(2024, 6, 15))
        assert SubscriptionService(sub).is_expired() is False

    @freeze_time("2024-06-15")
    def test_future_end_date_returns_false(self):
        sub = SubscriptionFactory(end_date=datetime.date(2024, 6, 16))
        assert SubscriptionService(sub).is_expired() is False


# ---------------------------------------------------------------------------
# has_remaining_credits
# ---------------------------------------------------------------------------


class TestHasRemainingCredits:
    def test_unlimited_shared_credits_returns_true(self):
        sub = SubscriptionFactory(credits=None)
        assert SubscriptionService(sub).has_remaining_credits() is True

    def test_positive_shared_credits_returns_true(self):
        sub = SubscriptionFactory(credits=5)
        assert SubscriptionService(sub).has_remaining_credits() is True

    def test_zero_shared_credits_no_balances_returns_false(self):
        sub = SubscriptionFactory(credits=0)
        assert SubscriptionService(sub).has_remaining_credits() is False

    def test_per_service_unlimited_credits_returns_true(self):
        sub = SubscriptionFactory(credits=0)
        SubscriptionCreditBalanceFactory(subscription=sub, credits=None)
        assert SubscriptionService(sub).has_remaining_credits() is True

    def test_per_service_positive_credits_returns_true(self):
        sub = SubscriptionFactory(credits=0)
        SubscriptionCreditBalanceFactory(subscription=sub, credits=3)
        assert SubscriptionService(sub).has_remaining_credits() is True

    def test_per_service_zero_credits_no_shared_returns_false(self):
        sub = SubscriptionFactory(credits=0)
        SubscriptionCreditBalanceFactory(subscription=sub, credits=0)
        assert SubscriptionService(sub).has_remaining_credits() is False


# ---------------------------------------------------------------------------
# can_access_service
# ---------------------------------------------------------------------------


class TestCanAccessService:
    def test_inactive_subscription_status_returns_false(self):
        sub = SubscriptionFactory(status=SubscriptionStatus.SUSPENDED, credits=10)
        service = ServiceFactory()
        assert SubscriptionService(sub).can_access_service(service) is False

    @freeze_time("2024-06-15")
    def test_expired_subscription_returns_false(self):
        sub = SubscriptionFactory(end_date=datetime.date(2024, 6, 14), credits=10)
        service = ServiceFactory()
        assert SubscriptionService(sub).can_access_service(service) is False

    def test_free_mode_unlimited_credits_returns_true_for_any_service(self):
        sub = SubscriptionFactory(credits=None)
        service = ServiceFactory()
        assert SubscriptionService(sub).can_access_service(service) is True

    def test_free_mode_positive_credits_returns_true(self):
        sub = SubscriptionFactory(credits=5)
        service = ServiceFactory()
        assert SubscriptionService(sub).can_access_service(service) is True

    def test_free_mode_zero_credits_returns_false(self):
        sub = SubscriptionFactory(credits=0)
        service = ServiceFactory()
        assert SubscriptionService(sub).can_access_service(service) is False

    def test_whitelist_mode_unlisted_service_returns_false(self):
        sub = SubscriptionFactory(credits=10)
        whitelisted = ServiceFactory()
        unlisted = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=whitelisted, credits=5)
        assert SubscriptionService(sub).can_access_service(unlisted) is False

    def test_whitelist_mode_listed_service_with_credits_returns_true(self):
        sub = SubscriptionFactory(credits=0)
        service = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=5)
        assert SubscriptionService(sub).can_access_service(service) is True

    def test_whitelist_mode_service_depleted_falls_back_to_shared(self):
        # Service-specific balance exhausted but shared pool has credits
        sub = SubscriptionFactory(credits=5)
        service = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=0)
        assert SubscriptionService(sub).can_access_service(service) is True

    def test_whitelist_mode_all_credits_exhausted_returns_false(self):
        sub = SubscriptionFactory(credits=0)
        service = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=0)
        assert SubscriptionService(sub).can_access_service(service) is False


# ---------------------------------------------------------------------------
# use_credit
# ---------------------------------------------------------------------------


class TestUseCredit:
    def test_free_mode_unlimited_returns_true_credits_unchanged(self):
        sub = SubscriptionFactory(credits=None)
        service = ServiceFactory()
        result = SubscriptionService(sub).use_credit(service)
        sub.refresh_from_db()
        assert result is True
        assert sub.credits is None

    def test_free_mode_decrements_shared_pool(self):
        sub = SubscriptionFactory(credits=5)
        service = ServiceFactory()
        result = SubscriptionService(sub).use_credit(service)
        sub.refresh_from_db()
        assert result is True
        assert sub.credits == 4

    def test_free_mode_zero_credits_returns_false(self):
        sub = SubscriptionFactory(credits=0)
        service = ServiceFactory()
        assert SubscriptionService(sub).use_credit(service) is False

    def test_whitelist_mode_decrements_service_balance(self):
        sub = SubscriptionFactory(credits=10)
        service = ServiceFactory()
        balance = SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=5)
        result = SubscriptionService(sub).use_credit(service)
        balance.refresh_from_db()
        assert result is True
        assert balance.credits == 4

    def test_whitelist_mode_service_exhausted_falls_back_to_shared(self):
        sub = SubscriptionFactory(credits=3)
        service = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=0)
        result = SubscriptionService(sub).use_credit(service)
        sub.refresh_from_db()
        assert result is True
        assert sub.credits == 2

    def test_whitelist_mode_unlisted_service_returns_false(self):
        sub = SubscriptionFactory(credits=10)
        whitelisted = ServiceFactory()
        unlisted = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=whitelisted, credits=5)
        assert SubscriptionService(sub).use_credit(unlisted) is False

    def test_whitelist_mode_all_exhausted_returns_false(self):
        sub = SubscriptionFactory(credits=0)
        service = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=0)
        assert SubscriptionService(sub).use_credit(service) is False


# ---------------------------------------------------------------------------
# restore_credit
# ---------------------------------------------------------------------------


class TestRestoreCredit:
    def test_free_mode_unlimited_returns_true_no_change(self):
        sub = SubscriptionFactory(credits=None)
        sub.subscription_type.credits = None
        sub.subscription_type.save()
        service = ServiceFactory()
        assert SubscriptionService(sub).restore_credit(service) is True

    def test_free_mode_below_max_increments_shared(self):
        # Factory default: subscription_type.credits=10, subscription.credits=3
        sub = SubscriptionFactory(credits=3)
        service = ServiceFactory()
        result = SubscriptionService(sub).restore_credit(service)
        sub.refresh_from_db()
        assert result is True
        assert sub.credits == 4

    def test_free_mode_at_max_returns_false(self):
        # credits already at the allocated ceiling
        sub = SubscriptionFactory(credits=10)
        service = ServiceFactory()
        assert SubscriptionService(sub).restore_credit(service) is False

    def test_whitelist_mode_restores_shared_credits_first(self):
        # shared pool is below its max (3 < 10), so shared gets restored first
        sub = SubscriptionFactory(credits=3)
        service = ServiceFactory()
        SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=0)
        result = SubscriptionService(sub).restore_credit(service)
        sub.refresh_from_db()
        assert result is True
        assert sub.credits == 4

    def test_whitelist_mode_restores_service_balance_when_shared_is_full(self):
        # shared pool already at max (10 == 10); restore goes to service balance
        sub = SubscriptionFactory(credits=10)
        service = ServiceFactory()
        st = sub.subscription_type
        SubscriptionTypeCreditAllocationFactory(subscription_type=st, service=service, credits=5)
        balance = SubscriptionCreditBalanceFactory(subscription=sub, service=service, credits=2)
        result = SubscriptionService(sub).restore_credit(service)
        balance.refresh_from_db()
        assert result is True
        assert balance.credits == 3


# ---------------------------------------------------------------------------
# can_renew
# ---------------------------------------------------------------------------


class TestCanRenew:
    @freeze_time("2024-06-15")
    def test_active_paid_expired_can_renew(self):
        sub = SubscriptionFactory(
            status=SubscriptionStatus.ACTIVE,
            is_paid=True,
            end_date=datetime.date(2024, 6, 14),
            credits=0,
        )
        assert SubscriptionService(sub).can_renew() is True

    def test_active_paid_credits_depleted_can_renew(self):
        sub = SubscriptionFactory(
            status=SubscriptionStatus.ACTIVE,
            is_paid=True,
            end_date=None,
            credits=0,
        )
        assert SubscriptionService(sub).can_renew() is True

    def test_not_paid_cannot_renew(self):
        sub = SubscriptionFactory(is_paid=False, credits=0)
        assert SubscriptionService(sub).can_renew() is False

    def test_non_active_status_cannot_renew(self):
        sub = SubscriptionFactory(status=SubscriptionStatus.CANCELLED, is_paid=True, credits=0)
        assert SubscriptionService(sub).can_renew() is False

    def test_still_has_credits_cannot_renew(self):
        sub = SubscriptionFactory(
            status=SubscriptionStatus.ACTIVE,
            is_paid=True,
            end_date=None,
            credits=5,
        )
        assert SubscriptionService(sub).can_renew() is False

    def test_inactive_subscription_type_cannot_renew(self):
        st = SubscriptionTypeFactory(is_active=False)
        sub = SubscriptionFactory(subscription_type=st, is_paid=True, credits=0)
        assert SubscriptionService(sub).can_renew() is False


# ---------------------------------------------------------------------------
# create_initial_credit_balances
# ---------------------------------------------------------------------------


class TestCreateInitialCreditBalances:
    def test_copies_shared_credits_from_type(self, subscription_type):
        subscription_type.credits = 15
        subscription_type.save()
        sub = SubscriptionFactory(subscription_type=subscription_type, credits=0)
        SubscriptionService(None).create_initial_credit_balances(sub)
        sub.refresh_from_db()
        assert sub.credits == 15

    def test_creates_one_balance_per_allocation(self, subscription_type, service):
        SubscriptionTypeCreditAllocationFactory(subscription_type=subscription_type, service=service, credits=8)
        sub = SubscriptionFactory(subscription_type=subscription_type)
        SubscriptionService(None).create_initial_credit_balances(sub)
        balance = sub.credit_balances.get(service=service)
        assert balance.credits == 8

    def test_none_allocation_credits_means_unlimited(self, subscription_type, service):
        SubscriptionTypeCreditAllocationFactory(subscription_type=subscription_type, service=service, credits=None)
        sub = SubscriptionFactory(subscription_type=subscription_type)
        SubscriptionService(None).create_initial_credit_balances(sub)
        balance = sub.credit_balances.get(service=service)
        assert balance.credits is None

    def test_inherits_unpaid_reservation_limit(self, subscription_type):
        subscription_type.unpaid_reservation_limit = 3
        subscription_type.save()
        sub = SubscriptionFactory(subscription_type=subscription_type, unpaid_reservation_limit=0)
        SubscriptionService(None).create_initial_credit_balances(sub)
        sub.refresh_from_db()
        assert sub.unpaid_reservation_limit == 3
