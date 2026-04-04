"""
Admin domain operation for marking a reservation as no-show.
"""

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction

from ....constants import ReservationStatus

if TYPE_CHECKING:
    from ....models import Reservation
    from ...base import ReservationService


class ReservationServiceAdminMarkNoShow:
    """
    Admin domain operation for marking a reservation as no-show.
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
        ]:
            raise ValidationError(
                f"Cannot mark reservation with status '{reservation.status}' as no-show. "
                "Only confirmed or completed reservations can be marked as no-show."
            )

        if reservation.event.is_cancelled:
            raise ValidationError(
                "Cannot mark reservation as no-show for a cancelled event."
            )

    def perform(self) -> "Reservation":
        reservation = self.service.reservation

        with transaction.atomic():
            reservation.status = ReservationStatus.NO_SHOW
            reservation.save(update_fields=["status"])

        return reservation

    def execute(self) -> "Reservation":
        self.authorize()
        self.validate()
        return self.perform()
