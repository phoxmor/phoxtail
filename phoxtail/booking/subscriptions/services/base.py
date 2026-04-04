from functools import cached_property
from typing import TYPE_CHECKING, Optional

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone

from phoxtail.booking.reservations.constants import ReservationStatus

if TYPE_CHECKING:
    from phoxtail.booking.services.models import Service

    from ..models import Subscription, SubscriptionType


User = get_user_model()


class SubscriptionTypeService:
    """
    Encapsulates business logic related to a SubscriptionType.
    """

    def __init__(self, subscription_type: "SubscriptionType") -> None:
        self.subscription_type = subscription_type

    def is_active(self) -> bool:
        """
        Checks if the subscription type is currently active and available for purchase.
        """
        return self.subscription_type.is_active

    def is_public(self) -> bool:
        """
        Checks if the subscription type is currently public.
        """
        return self.subscription_type.is_public


class SubscriptionService:
    """
    Core service for Subscription model operations.

    Provides generic business logic for subscriptions including credit management,
    access validation, and reservation limits. Delegates domain-specific operations
    to child services (admin, public).

    Usage:
        # For creation (no existing subscription):
        subscription = SubscriptionService().admin.create(user, subscription_type)

        # For operations on existing subscriptions:
        SubscriptionService(subscription).admin.renew()
        SubscriptionService(subscription).admin.cancel()
    """

    def __init__(self, subscription: Optional["Subscription"] = None) -> None:
        self.subscription = subscription

    # Domain-specific business logic gateways
    @cached_property
    def admin(self):
        """Access admin domain operations"""
        from .admin import SubscriptionServiceAdminGateway

        return SubscriptionServiceAdminGateway(self)

    @cached_property
    def public(self):
        """Access public domain operations"""
        from .public import SubscriptionServicePublicGateway

        return SubscriptionServicePublicGateway(self)

    # Base business logic
    def get_credits_for_service(self, service: "Service") -> int | None:
        """
        Get remaining credits for a specific service.
        Returns float('inf') for unlimited credits, 0 for no access or no credits.
        """
        try:
            allocation = self.subscription.subscription_type.credit_allocations.get(
                service=service
            )

            if allocation.credits is None:
                return float("inf")

            balance = self.subscription.credit_balances.get(service=service)
            return balance.credits
        except models.ObjectDoesNotExist:
            return 0

    def use_credit(self, service: "Service") -> bool:
        """
        Use one credit for a specific service atomically.
        Returns True if credit was successfully used (or unlimited), False otherwise.
        """
        with transaction.atomic():
            # Lock the subscription row to prevent concurrent modifications
            subscription = self.subscription.__class__.objects.select_for_update().get(
                pk=self.subscription.pk
            )

            credits = subscription.credits
            balances = subscription.credit_balances

            # No whitelist exists - use shared credits for any service
            if not balances.exists():
                if credits is None:
                    return True  # Unlimited shared credits
                if credits > 0:
                    subscription.credits -= 1
                    subscription.save(update_fields=["credits"])
                    return True
                return False  # No shared credits left

            # Whitelist mode - lock and check service-specific balance
            balance = balances.select_for_update().filter(service=service).first()
            if not balance:
                return False  # Service not whitelisted

            # Try service-specific credits first
            if balance.credits is None:
                return True  # Unlimited access to this service

            if balance.credits > 0:
                balance.credits -= 1
                balance.save(update_fields=["credits"])
                return True

            # Fall back to shared credits (only limited, never unlimited)
            if credits is not None and credits > 0:
                subscription.credits -= 1
                subscription.save(update_fields=["credits"])
                return True

            return False  # No credits available

    def can_access_service(
        self, service: "Service", skip_credit_validation=False, skip_active_check=False
    ) -> bool:
        """
        Check if the subscription can access a specific service.
        Considers overall subscription activity, duration, and credit balances.

        Args:
            service: The service to check access for
            skip_credit_validation: If True, skip checking remaining credit balances
            skip_active_check: If True, skip checking if subscription is active
        """
        from ..constants import SubscriptionStatus

        if (
            not skip_active_check
            and self.subscription.status != SubscriptionStatus.ACTIVE
        ):
            return False

        if skip_credit_validation:
            return True

        if self.subscription.is_expired:
            return False

        credits = self.subscription.credits
        balances = self.subscription.credit_balances

        # No whitelist exists - unlimited access to all services
        if not balances.exists():
            return credits is None or (credits is not None and credits > 0)

        # Whitelist mode - check if service is whitelisted and has access
        balance = balances.filter(service=service).first()
        if not balance:
            return False  # Service not whitelisted

        # Service is whitelisted - check credits
        if balance.credits is None:
            return True  # Unlimited access to this service

        if balance.credits > 0:
            return True  # Has remaining service-specific credits

        # Fall back to shared credits if available (only limited credits, never unlimited)
        return credits is not None and credits > 0

    def restore_credit(self, service: "Service") -> bool:
        """
        Restore one credit for a specific service when a reservation is cancelled.
        Restoration order: Shared credits first, then service-specific credits.
        Returns True if credit was successfully restored, False otherwise.
        """
        with transaction.atomic():
            # Lock subscription and get fresh data
            subscription = self.subscription.__class__.objects.select_for_update().get(
                pk=self.subscription.pk
            )

            credits = subscription.credits
            allocated_credits = subscription.subscription_type.credits
            balances = subscription.credit_balances

            # No whitelist exists - restore to shared credits only
            if not balances.exists():
                if credits is None or allocated_credits is None:
                    return True  # Unlimited - nothing to restore
                if credits < allocated_credits:
                    subscription.credits += 1
                    subscription.save(update_fields=["credits"])
                    return True
                return False  # Already at max

            # Whitelist mode - restore shared credits FIRST, then service-specific
            balance = balances.select_for_update().filter(service=service).first()
            if not balance:
                return False  # Service not whitelisted

            # Step 1: Try to restore shared credits first (if limited)
            if (
                credits is not None
                and allocated_credits is not None
                and credits < allocated_credits
            ):
                subscription.credits += 1
                subscription.save(update_fields=["credits"])
                return True

            # Step 2: If shared credits are full/unlimited, restore service-specific
            balance_allocated = (
                subscription.subscription_type.credit_allocations.filter(
                    service=service
                ).first()
            )

            if balance.credits is None or (
                balance_allocated and balance_allocated.credits is None
            ):
                return True  # Unlimited service - nothing to restore

            if balance_allocated and balance_allocated.credits is not None:
                if balance.credits < balance_allocated.credits:
                    balance.credits += 1
                    balance.save(update_fields=["credits"])
                    return True

            return False  # Both pools are full or at max

    def get_user_first_name(self):
        """Get the first name of the subscription user."""
        return self.subscription.user.first_name

    def get_user_last_name(self):
        """Get the last name of the subscription user."""
        return self.subscription.user.last_name

    def get_user_username(self):
        """Get the username of the subscription user."""
        return self.subscription.user.username

    def get_user_email(self):
        """Get the email of the subscription user."""
        return self.subscription.user.email

    def get_subscription_type_name(self):
        """Get the subscription type name."""
        return self.subscription.subscription_type.name

    def is_expired(self) -> bool:
        """
        Check if the subscription has expired based on time.

        A subscription is considered expired if it's duration-based (has end_date)
        and the end_date has passed.

        Returns:
            True if end_date has passed, False otherwise (including if no end_date)
        """
        if self.subscription.end_date is None:
            return False

        return self.subscription.end_date < timezone.now().date()

    def has_remaining_shared_credits(self) -> bool:
        """
        Check if the subscription has any remaining shared credits.

        Returns:
            True if unlimited shared credits OR shared credits > 0, False otherwise
        """
        subscription = self.subscription

        # Check shared credits pool
        if subscription.credits is None:
            # Unlimited shared credits
            return True

        return subscription.credits > 0

    def has_remaining_per_service_credits(
        self, service: Optional["Service"] = None
    ) -> bool:
        """
        Check if the subscription has any remaining per-service credits.

        Args:
            service: Optional specific service to check. If None, checks if ANY
                     per-service balance has remaining credits.

        Returns:
            True if unlimited credits OR any credits remaining for the service(s),
            False if depleted or service not found
        """
        subscription = self.subscription
        balances = subscription.credit_balances.all()

        if not balances.exists():
            # No per-service balances
            return False

        # If a specific service is provided, check only that service
        if service is not None:
            balance = balances.filter(service=service).first()
            if not balance:
                return False  # Service not found in balances

            if balance.credits is None:
                return True  # Unlimited credits for this service

            return balance.credits > 0

        # Check if any per-service balance has credits remaining
        for balance in balances:
            if balance.credits is None:
                # Unlimited credits for this service
                return True
            if balance.credits > 0:
                return True

        return False

    def has_remaining_credits(self) -> bool:
        """
        Check if the subscription has any remaining credits available.

        This checks both:
        1. Shared credits pool
        2. Per-service credit balances

        Returns:
            True if unlimited credits OR any credits remaining, False if depleted
        """
        # Check shared credits pool
        if self.has_remaining_shared_credits():
            return True

        # Check per-service credit balances
        return self.has_remaining_per_service_credits()

    def get_unpaid_reservation_limit(self) -> int:
        """
        Get the unpaid reservation limit for this subscription.
        The limit is set during subscription creation from the subscription type.
        """
        return self.subscription.unpaid_reservation_limit

    def get_unpaid_reservation_count(self) -> int:
        """
        Count the number of active reservations for this unpaid subscription.
        Only counts reservations if the subscription is not paid.
        """
        if self.subscription.is_paid:
            return 0

        return self.subscription.reservations.filter(
            status__in=[
                ReservationStatus.CONFIRMED,
                ReservationStatus.COMPLETED,
                ReservationStatus.CANCELLED,
            ]
        ).count()

    def can_access_grace_period_reservations(self) -> bool:
        """
        Check if the user can make another reservation based on unpaid reservation grace period limits.
        Returns True if subscription is paid or within unpaid reservation limit.
        """
        # Paid subscriptions have no reservation limits
        if self.subscription.is_paid:
            return True

        limit = self.get_unpaid_reservation_limit()
        current_count = self.get_unpaid_reservation_count()

        return current_count < limit

    def get_remaining_grace_period_reservations(self) -> int:
        """
        Calculate the number of grace period reservations remaining for an unpaid subscription.
        Grace period allows users to make limited reservations before payment is required.

        Returns:
            Number of remaining reservations before payment required (0 if paid or limit reached)
        """
        # Paid subscriptions don't have grace period limits
        if self.subscription.is_paid:
            return 0

        limit = self.get_unpaid_reservation_limit()
        current_count = self.get_unpaid_reservation_count()

        remaining = limit - current_count
        return max(0, remaining)  # Ensure non-negative

    def can_renew(self) -> bool:
        """
        Check if the subscription can be renewed.

        A subscription can be renewed when:
        - It's in ACTIVE status
        - The subscription type is still active
        - It's been paid for
        - Either the subscription has expired OR credits are depleted (not both active AND has credits)

        Returns:
            True if subscription can be renewed, False otherwise
        """
        from ..constants import SubscriptionStatus

        subscription = self.subscription
        subscription_type = subscription.subscription_type

        # Must be in ACTIVE status
        if subscription.status != SubscriptionStatus.ACTIVE:
            return False

        # Subscription type must still be active
        if not subscription_type.service.is_active():
            return False

        # Must be paid
        if not subscription.is_paid:
            return False

        # Can only renew if expired OR credits depleted
        # Cannot renew if still active AND has remaining credits
        if not self.is_expired() and self.has_remaining_credits():
            return False

        return True

    def get_renewal_end_date(self):
        """
        Calculate what the end date would be for a renewed subscription.
        Uses the subscription type's duration and location's timezone.

        Returns:
            date object if duration exists, None for unlimited subscriptions
        """
        from datetime import timedelta

        subscription_type = self.subscription.subscription_type

        # No duration means unlimited subscription
        if subscription_type.duration is None:
            return None

        # Get today's date in the location's timezone
        location_tz = subscription_type.location.timezone
        start_date = timezone.now().astimezone(location_tz).date()

        # Calculate end date
        end_date = start_date + timedelta(days=subscription_type.duration)
        return end_date

    def is_event_within_subscription_period(
        self, event_start_datetime: timezone.datetime
    ) -> bool:
        """
        Checks if an event falls within the subscription's valid period.

        Args:
            event_start_datetime: The start time of the event (datetime)

        Returns:
            bool: True if event is within subscription period, False otherwise
        """
        event_date = event_start_datetime.date()

        # Check if event is within subscription period
        if event_date < self.subscription.start_date:
            return False

        # Check end date - null end_date means unlimited access
        if self.subscription.end_date and event_date > self.subscription.end_date:
            return False

        return True

    def create_initial_credit_balances(self, subscription: "Subscription") -> None:
        """
        Initialize subscription credits and create balance records when subscription is created.

        This is a domain-agnostic operation used by both admin and public subscription creation.

        Args:
            subscription: The subscription to initialize credits for
        """
        subscription_type = subscription.subscription_type

        # Migrate shared credits from subscription type
        subscription.credits = subscription_type.credits

        # Inherit unpaid reservation limit from subscription type if not set
        if not subscription.unpaid_reservation_limit:
            subscription.unpaid_reservation_limit = (
                subscription_type.unpaid_reservation_limit
            )

        subscription.save(update_fields=["credits", "unpaid_reservation_limit"])

        # Create balance entries for all allocations (acts as service whitelist for shared credits)
        for allocation in subscription_type.credit_allocations.all():
            subscription.credit_balances.get_or_create(
                service=allocation.service,
                subscription=subscription,
                defaults={"credits": allocation.credits},
            )
