"""
Gateway to all admin domain operations for reservations.
"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model

from .operations import (
    ReservationServiceAdminCancel,
    ReservationServiceAdminComplete,
    ReservationServiceAdminConfirm,
    ReservationServiceAdminCreate,
    ReservationServiceAdminMarkNoShow,
    ReservationServiceAdminMove,
    ReservationServiceAdminRevertWaitlisted,
)

if TYPE_CHECKING:
    from ...models import Reservation
    from ..base import ReservationService


User = get_user_model()


class ReservationServiceAdminGateway:
    """
    Gateway to all admin domain operations for reservations.

    Provides namespaced access to admin-specific services like
    create, cancel, move, confirm, complete, and revert_to_waitlisted.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def create(
        self,
        user_id: str,
        event_id: str,
        subscription_id: str,
        status: str = "CONFIRMED",
    ) -> "Reservation":
        """
        Create a new reservation for a user (admin-triggered).

        Args:
            user_id: ID of the user to create reservation for
            event_id: ID of the event to reserve
            subscription_id: Subscription to use for the reservation
            status: Status for the new reservation

        Returns:
            The created Reservation instance

        Raises:
            ValidationError: If reservation cannot be created
        """
        operation = ReservationServiceAdminCreate(self.service)
        return operation.execute(
            user_id=user_id,
            event_id=event_id,
            subscription_id=subscription_id,
            reservation_status=status,
        )

    def cancel(self, user: User) -> None:
        """
        Cancel the reservation.

        Args:
            user: The user making the cancellation request

        Raises:
            ValidationError: If cancellation cannot be processed
        """
        operation = ReservationServiceAdminCancel(self.service)
        return operation.execute(user=user)

    def move(
        self,
        target_event_id: str,
        skip_credit_validation: bool = False,
        skip_active_check: bool = False,
    ) -> "Reservation":
        """
        Move the reservation to a different event.

        Args:
            target_event_id: ID of the target event
            skip_credit_validation: Skip credit balance checks
            skip_active_check: Skip subscription active status check

        Returns:
            The updated Reservation instance

        Raises:
            ValidationError: If move cannot be completed
        """
        operation = ReservationServiceAdminMove(self.service)
        return operation.execute(
            target_event_id=target_event_id,
            skip_credit_validation=skip_credit_validation,
            skip_active_check=skip_active_check,
        )

    def confirm(self, subscription_id: str | None = None) -> "Reservation":
        """
        Confirm a waitlisted or cancelled reservation.

        Args:
            subscription_id: Optional subscription to use (required for waitlisted)

        Returns:
            The updated Reservation instance

        Raises:
            ValidationError: If confirmation cannot be completed
        """
        operation = ReservationServiceAdminConfirm(self.service)
        return operation.execute(subscription_id=subscription_id)

    def complete(self) -> "Reservation":
        """
        Complete a confirmed reservation (mark attendance).

        Returns:
            The updated Reservation instance

        Raises:
            ValidationError: If completion cannot be processed
        """
        operation = ReservationServiceAdminComplete(self.service)
        return operation.execute()

    def mark_no_show(self) -> "Reservation":
        """
        Mark a confirmed/completed reservation as no-show.

        Returns:
            The updated Reservation instance

        Raises:
            ValidationError: If marking as no-show cannot be processed
        """
        operation = ReservationServiceAdminMarkNoShow(self.service)
        return operation.execute()

    def revert_to_waitlisted(self) -> "Reservation":
        """
        Revert a confirmed/completed reservation back to waitlisted status.
        Restores subscription credit if applicable.

        Returns:
            The updated Reservation instance

        Raises:
            ValidationError: If revert cannot be processed
        """
        operation = ReservationServiceAdminRevertWaitlisted(self.service)
        return operation.execute()
