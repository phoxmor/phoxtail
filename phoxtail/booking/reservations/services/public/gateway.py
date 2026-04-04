"""
Gateway to all public domain operations for reservations.
"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model

from .operations import (
    ReservationServicePublicConfirmWaitlisted,
    ReservationServicePublicCreate,
    ReservationServicePublicCreateWaitlisted,
)

if TYPE_CHECKING:
    from ...models import Reservation
    from ..base import ReservationService


User = get_user_model()


class ReservationServicePublicGateway:
    """
    Gateway to all public domain operations for reservations.

    Provides namespaced access to public-facing services like
    create, create_waitlisted, and confirm_waitlisted.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def create(
        self,
        user: User,
        event_id: str,
        subscription_id: str | None = None,
    ) -> "Reservation":
        """
        Create a new reservation for the user.

        Args:
            user: The user making the reservation
            event_id: ID of the event to reserve
            subscription_id: Optional subscription to use

        Returns:
            The created Reservation instance

        Raises:
            ValidationError: If reservation cannot be created
        """
        operation = ReservationServicePublicCreate(self.service)
        return operation.execute(
            user=user,
            event_id=event_id,
            subscription_id=subscription_id,
        )

    def create_waitlisted(
        self,
        user: User,
        event_id: str,
        subscription_id: str,
    ) -> "Reservation":
        """
        Create a waitlisted reservation for the user.

        Args:
            user: The user making the reservation
            event_id: ID of the event to reserve
            subscription_id: Subscription to bind to the reservation

        Returns:
            The created Reservation instance with WAITLISTED status

        Raises:
            ValidationError: If reservation cannot be created
        """
        operation = ReservationServicePublicCreateWaitlisted(self.service)
        return operation.execute(
            user=user,
            event_id=event_id,
            subscription_id=subscription_id,
        )

    def confirm_waitlisted(
        self,
        user: User,
        reservation_id: str,
        subscription_id: str | None = None,
    ) -> "Reservation":
        """
        Confirm a waitlisted reservation by using subscription credits.

        Args:
            user: The user confirming the reservation
            reservation_id: ID of the waitlisted reservation
            subscription_id: Optional subscription to use

        Returns:
            The updated Reservation instance with CONFIRMED status

        Raises:
            ValidationError: If reservation cannot be confirmed
        """
        operation = ReservationServicePublicConfirmWaitlisted(self.service)
        return operation.execute(
            user=user,
            reservation_id=reservation_id,
            subscription_id=subscription_id,
        )
