"""
Admin domain operation for reservation cancellation.
"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ....constants import ReservationStatus

if TYPE_CHECKING:
    from ...base import ReservationService


User = get_user_model()


class ReservationServiceAdminCancel:
    """
    Admin domain operation for reservation cancellation.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self) -> None:
        pass

    def perform(self, user: User) -> None:
        reservation = self.service.reservation

        allowed_cancellation_period = (
            reservation.event.start_datetime
            - timezone.timedelta(
                hours=reservation.event.service.cancellation_lockout_hours
            )
        )

        with transaction.atomic():
            # Allowed cancellation period - delete the reservation and restore credit
            if timezone.now() < allowed_cancellation_period:
                # Restore credit if subscription was used and not waitlisted
                if (
                    reservation.status != ReservationStatus.WAITLISTED
                    and reservation.subscription
                ):
                    reservation.subscription.service.restore_credit(
                        reservation.event.service
                    )

                reservation.delete()
            else:
                # Outside allowed cancellation period - mark as cancelled
                reservation.status = ReservationStatus.CANCELLED
                reservation.save(update_fields=["status"])

    def execute(self, user: User) -> None:
        self.authorize()
        self.validate()
        self.perform(user=user)
