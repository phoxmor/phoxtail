from datetime import date
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model

from .operations import SubscriptionServicePublicCreate, SubscriptionServicePublicRenew

if TYPE_CHECKING:
    from .. import SubscriptionService
    from ..models import Subscription, SubscriptionType


User = get_user_model()


class SubscriptionServicePublicGateway:
    """
    Gateway to all public domain operations for subscriptions.

    Provides namespaced access to public-facing services like create, etc.
    """

    def __init__(self, service: "SubscriptionService") -> None:
        self.service = service

    def create(
        self,
        user: User,
        subscription_type: "SubscriptionType",
        start_date: date | None = None,
    ) -> "Subscription":
        """
        Create a new subscription for a user (public-facing).

        Args:
            user: The user to create the subscription for
            subscription_type: The subscription type to create
            start_date: Optional start date (defaults to today in subscription type's location timezone)

        Returns:
            The created Subscription instance

        Raises:
            ValidationError: If subscription cannot be created
        """

        operation = SubscriptionServicePublicCreate(self.service)

        return operation.execute(
            user=user,
            subscription_type=subscription_type,
            start_date=start_date,
        )

    def renew(self, start_date: date | None = None) -> "Subscription":
        """
        Renew an existing subscription (public-facing).

        Archives the current subscription and creates a new one with fresh credits.
        Requires the subscription to be set on the parent SubscriptionService.

        Args:
            start_date: Optional start date for the new subscription period
                       (defaults to today in subscription type's location timezone)

        Returns:
            The newly created Subscription instance

        Raises:
            ValidationError: If subscription cannot be renewed
        """

        operation = SubscriptionServicePublicRenew(self.service)

        return operation.execute(start_date=start_date)
