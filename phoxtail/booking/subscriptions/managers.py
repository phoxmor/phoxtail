from django.db import models
from django.utils import timezone


class SubscriptionTypeManager(models.Manager):
    def public(self):
        """Returns subscription types that are active and public."""
        return self.filter(is_active=True, is_public=True)


class SubscriptionManager(models.Manager):
    def active(self):
        """
        Returns subscriptions with status=ACTIVE.
        These can potentially be used for reservations (still need to check expiration).
        """
        from .constants import SubscriptionStatus

        return self.filter(status=SubscriptionStatus.ACTIVE)

    def not_expired(self):
        """
        Returns subscriptions that have not expired based on end_date.
        A subscription is not expired if:
        - end_date is None (unlimited duration), OR
        - end_date is today or in the future
        """
        today = timezone.now().date()
        return self.filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        )

    def active_and_not_expired(self):
        """
        Returns subscriptions that are active AND not expired.
        This is the main method to use when checking for valid user subscriptions.
        """
        return self.active().filter(
            models.Q(end_date__isnull=True)
            | models.Q(end_date__gte=timezone.now().date())
        )

    def archived(self):
        """Returns subscriptions that have been archived."""
        from .constants import SubscriptionStatus

        return self.filter(status=SubscriptionStatus.ARCHIVED)

    def frozen(self):
        """Returns subscriptions that are currently frozen."""
        from .constants import SubscriptionStatus

        return self.filter(status=SubscriptionStatus.FROZEN)

    def suspended(self):
        """Returns subscriptions that have been suspended."""
        from .constants import SubscriptionStatus

        return self.filter(status=SubscriptionStatus.SUSPENDED)

    def cancelled(self):
        """Returns subscriptions that have been cancelled."""
        from .constants import SubscriptionStatus

        return self.filter(status=SubscriptionStatus.CANCELLED)

    def can_access_service(self, service):
        """
        Returns subscriptions that are active, not expired, AND can access the specific service.
        """
        eligible_subscriptions = self.active_and_not_expired()

        from django.db.models import Q

        # Case 1: No whitelist exists - unlimited access to all services with shared credits
        unlimited_access = Q(credit_balances__isnull=True) & (
            Q(credits__isnull=True) | Q(credits__gt=0)
        )

        # Case 2: Service is whitelisted with unlimited access
        service_unlimited = Q(credit_balances__service=service) & Q(
            credit_balances__credits__isnull=True
        )

        # Case 3: Service is whitelisted with remaining service-specific credits
        service_has_credits = Q(credit_balances__service=service) & Q(
            credit_balances__credits__gt=0
        )

        # Case 4: Service is whitelisted but can fall back to shared credits
        # This handles when service has 0 service-specific credits but subscription has shared credits
        service_fallback = Q(credit_balances__service=service) & Q(credits__gt=0)

        return eligible_subscriptions.filter(
            unlimited_access
            | service_unlimited
            | service_has_credits
            | service_fallback
        ).distinct()
