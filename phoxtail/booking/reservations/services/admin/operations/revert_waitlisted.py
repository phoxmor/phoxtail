"""
Admin domain operation for reverting a reservation to waitlisted status.
"""

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction

from ....constants import ReservationStatus

if TYPE_CHECKING:
    from ....models import Reservation
    from ...base import ReservationService


class ReservationServiceAdminRevertWaitlisted:
    """
    Admin domain operation for reverting a confirmed/completed reservation
    back to waitlisted status, restoring subscription credit if applicable.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self) -> None:
        reservation = self.service.reservation

        if reservation.status not in [
            ReservationStatus.CONFIRMED,
            ReservationStatus.COMPLETED,
            ReservationStatus.NO_SHOW,
        ]:
            raise ValidationError(
                f"Cannot revert reservation with status '{reservation.status}' to waitlisted. "
                "Only confirmed, completed, or no-show reservations can be reverted."
            )

    def perform(self) -> "Reservation":
        reservation = self.service.reservation

        with transaction.atomic():
            # Restore credit if subscription was used
            if reservation.subscription:
                reservation.subscription.service.restore_credit(reservation.event.service)
            reservation.status = ReservationStatus.WAITLISTED
            reservation.save(update_fields=["status"])

        return reservation

    def execute(self) -> "Reservation":
        self.authorize()
        self.validate()
        return self.perform()
