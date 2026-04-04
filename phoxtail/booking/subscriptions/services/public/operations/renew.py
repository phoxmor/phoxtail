from datetime import date
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from ....constants import SubscriptionStatus
from .create import SubscriptionServicePublicCreate

if TYPE_CHECKING:
    from .... import SubscriptionService
    from ....models import Subscription


User = get_user_model()


class SubscriptionServicePublicRenew:
    """
    Public domain operation for subscription renewal.

    Renews a subscription by archiving the current subscription instance and
    creating a new one with fresh credits and updated dates.
    """

    def __init__(self, service: "SubscriptionService") -> None:
        self.service = service

    def authorize(self, user: User) -> None:
        pass

    def validate(self) -> None:
        subscription = self.service.subscription
        subscription_type = subscription.subscription_type

        # Validation 1: Subscription must exist
        if subscription is None:
            raise ValidationError(_("No subscription provided for renewal."))

        # Validation 2: Subscription type must still be active
        if not subscription_type.service.is_active():
            raise ValidationError(_("This subscription is currently unavailable."))

        # Validation 3: Subscription type must be public
        if not subscription_type.service.is_public():
            raise ValidationError(_("This subscription is not available for renewal."))

        # Validation 4: Subscription must be in a renewable status
        # Only ACTIVE subscriptions can be renewed (not CANCELLED, SUSPENDED, etc.)
        renewable_statuses = [SubscriptionStatus.ACTIVE]
        if subscription.status not in renewable_statuses:
            raise ValidationError(
                _("This subscription cannot be renewed due to its current status.")
            )

        # Validation 5: Can only renew if expired OR credits depleted
        # Block renewal only when subscription is still active AND has remaining credits
        if not self.service.is_expired() and self.service.has_remaining_credits():
            raise ValidationError(
                _(
                    "Your subscription is still active with remaining credits. "
                    "You can renew after your subscription expires or you use all your credits."
                )
            )

        # Validation 6: Subscription must be paid before renewal
        if not subscription.is_paid:
            raise ValidationError(
                _(
                    "This subscription has not been paid for. "
                    "Please complete the payment before renewing."
                )
            )

    def perform(self, start_date: date) -> "Subscription":
        old_subscription = self.service.subscription
        subscription_type = old_subscription.subscription_type
        user = old_subscription.user

        with transaction.atomic():
            # Step 1: Archive the old subscription
            old_subscription.status = SubscriptionStatus.ARCHIVED
            old_subscription.save(update_fields=["status"])

            # Step 2: Delegate to the Create operation for new subscription
            create_operation = SubscriptionServicePublicCreate(self.service)
            new_subscription = create_operation.perform(
                user=user,
                subscription_type=subscription_type,
                start_date=start_date,
            )

        return new_subscription

    def execute(self, start_date: date | None = None) -> "Subscription":
        subscription = self.service.subscription
        subscription_type = subscription.subscription_type

        if start_date is None:
            # Default to today in the location's timezone
            location_tz = subscription_type.location.timezone
            start_date = timezone.now().astimezone(location_tz).date()

        self.authorize(subscription.user)
        self.validate()

        return self.perform(start_date)
