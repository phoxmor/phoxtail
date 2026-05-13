from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from ....constants import SubscriptionStatus

if TYPE_CHECKING:
    from .... import SubscriptionService
    from ....models import Subscription, SubscriptionType


User = get_user_model()


class SubscriptionServicePublicCreate:
    """
    Public domain operation for subscription creation.
    """

    def __init__(self, service: "SubscriptionService") -> None:
        self.service = service

    def authorize(self, user: User) -> None:
        pass

    def validate(self, user: User, subscription_type: "SubscriptionType") -> None:
        from ....models import Subscription

        # Validation 1: Do not allow to subscribe to an inactive subscription type
        if not subscription_type.service.is_active():
            raise ValidationError(_("This subscription is currently unavailable."))

        # Validation 2: Do not allow to subscribe to a non-public subscription type
        if not subscription_type.service.is_public():
            raise ValidationError(_("This subscription is not available for purchase."))

        # Validation 3: Check if user has unpaid subscriptions
        if Subscription.objects.filter(user=user, is_paid=False).exists():
            raise ValidationError(_("You have unpaid plans. Please complete payment before purchasing a new plan."))

        # Validation 4: Check if user already has an ACTIVE subscription of the same type
        # (Archived/cancelled subscriptions don't count as duplicates)
        if Subscription.objects.filter(
            user=user,
            subscription_type=subscription_type,
            status=SubscriptionStatus.ACTIVE,
        ).exists():
            raise ValidationError(_(f"You already have an active '{subscription_type.name}' subscription."))

    def perform(
        self,
        user: User,
        subscription_type: "SubscriptionType",
        start_date: date,
    ) -> "Subscription":
        from ....models import Subscription

        with transaction.atomic():
            # Create the subscription instance
            subscription = Subscription(
                user=user,
                subscription_type=subscription_type,
                start_date=start_date,
            )

            # Set end date if duration-based
            if subscription_type.duration is not None:
                subscription.end_date = start_date + timedelta(days=subscription_type.duration)

            # Save the subscription
            subscription.save()

            # Initialize credit balances using the base service
            self.service.create_initial_credit_balances(subscription)

        return subscription

    def execute(
        self,
        user: User,
        subscription_type: "SubscriptionType",
        start_date: date | None = None,
    ) -> "Subscription":
        if start_date is None:
            # Use the subscription type's location timezone for the correct local date
            location_tz = subscription_type.location.timezone
            now_in_location_tz = timezone.now().astimezone(location_tz)
            start_date = now_in_location_tz.date()

        self.authorize(user)
        self.validate(user, subscription_type)

        return self.perform(user, subscription_type, start_date)
