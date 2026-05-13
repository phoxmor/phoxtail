"""
Base service and validator for reservation business logic.
"""

from functools import cached_property
from typing import TYPE_CHECKING, Optional

from django.core.exceptions import ValidationError
from django.utils import timezone

if TYPE_CHECKING:
    from phoxtail.booking.subscriptions.models import Subscription

    from ..models import Reservation


class ReservationService:
    """Service class for Reservation business logic."""

    def __init__(self, reservation: Optional["Reservation"] = None) -> None:
        self.reservation = reservation

    @cached_property
    def admin(self):
        """Access admin domain operations."""
        from .admin import ReservationServiceAdminGateway

        return ReservationServiceAdminGateway(self)

    @cached_property
    def public(self):
        """Access public domain operations."""
        from .public import ReservationServicePublicGateway

        return ReservationServicePublicGateway(self)

    def get_user_username(self):
        """Get the username of the reservation user."""
        return self.reservation.user.username

    def get_user_first_name(self):
        """Get the first name of the reservation user."""
        return self.reservation.user.first_name

    def get_user_last_name(self):
        """Get the last name of the reservation user."""
        return self.reservation.user.last_name

    def get_user_email(self):
        """Get the email of the reservation user."""
        return self.reservation.user.email

    def get_user_full_name(self):
        """Get the full name of the reservation user."""
        return self.reservation.user.get_full_name()

    def get_event_service_name(self):
        """Get the service name of the reserved event."""
        return self.reservation.event.service.name

    def get_event_title(self):
        """Get the title of the reserved event."""
        return self.reservation.event.title

    def is_cancelled(self) -> bool:
        """Check if the reservation is cancelled."""
        from ..constants import ReservationStatus

        return self.reservation.status == ReservationStatus.CANCELLED

    def get_is_within_allowed_cancellation_period(self):
        """
        Determines if the reservation is within the allowed cancellation period.

        When within this period:
        - Reservation will be deleted upon cancellation
        - Credit will be restored (if applicable)

        When outside this period:
        - Reservation will be marked as cancelled
        - No credit restoration will occur

        Returns:
            bool: True if within allowed cancellation period, False otherwise
        """
        allowed_cancellation_period = self.reservation.event.start_datetime - timezone.timedelta(
            hours=self.reservation.event.service.cancellation_lockout_hours
        )
        return timezone.now() < allowed_cancellation_period


class ReservationValidator:
    """Validator class for reservation business logic validations."""

    @staticmethod
    def validate_grace_period_access(subscription: Optional["Subscription"]) -> None:
        """
        Validates that the subscription allows reservation creation based on grace period rules.

        Args:
            subscription: The subscription to validate (can be None)

        Raises:
            ValidationError: If subscription has exhausted grace period reservations
        """
        if subscription and not subscription.service.can_access_grace_period_reservations():
            raise ValidationError(
                "This plan has reached its grace period limit. Payment is required for more bookings."
            )
