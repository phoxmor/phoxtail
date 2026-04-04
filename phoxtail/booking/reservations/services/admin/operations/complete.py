"""
Admin domain operation for reservation completion.
"""

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction

from ....constants import ReservationStatus

if TYPE_CHECKING:
    from ....models import Reservation
    from ...base import ReservationService


class ReservationServiceAdminComplete:
    """
    Admin domain operation for reservation completion.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self) -> None:
        reservation = self.service.reservation

        # Only confirmed or no-show reservations can be completed
        if reservation.status not in [
            ReservationStatus.CONFIRMED,
            ReservationStatus.NO_SHOW,
        ]:
            raise ValidationError(
                f"Cannot complete reservation with status '{reservation.status}'. "
                "Only confirmed or no-show reservations can be completed."
            )

        # Check if event is cancelled
        if reservation.event.is_cancelled:
            raise ValidationError("Cannot complete reservation for a cancelled event.")

    def perform(self) -> "Reservation":
        reservation = self.service.reservation

        with transaction.atomic():
            reservation.status = ReservationStatus.COMPLETED
            reservation.save(update_fields=["status"])

        return reservation

    def execute(self) -> "Reservation":
        self.authorize()
        self.validate()
        return self.perform()
