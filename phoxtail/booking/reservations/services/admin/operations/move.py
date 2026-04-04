"""
Admin domain operation for reservation move.
"""

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction

from ....constants import ReservationStatus

if TYPE_CHECKING:
    from ....models import Reservation
    from ...base import ReservationService


class ReservationServiceAdminMove:
    """
    Admin domain operation for moving a reservation to a different event.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(
        self,
        target_event,
        skip_credit_validation: bool = False,
        skip_active_check: bool = False,
    ) -> None:
        from ....models import Reservation

        reservation = self.service.reservation

        # Cannot move to the same event
        if reservation.event.id == target_event.id:
            raise ValidationError("Cannot move reservation to the same event.")

        # Check if target event is cancelled
        if target_event.is_cancelled:
            raise ValidationError("Cannot move to a cancelled event.")

        # Check if user has access to target event
        if target_event.user_can_access_event(reservation.user) is False:
            raise ValidationError(
                "User does not have the required level to access the target event."
            )

        # Check for duplicate reservation in target event
        existing_reservation = Reservation.objects.filter(
            user=reservation.user,
            event=target_event,
        ).first()

        if existing_reservation:
            if existing_reservation.status == ReservationStatus.COMPLETED:
                raise ValidationError("User already attended the target event.")
            elif existing_reservation.status == ReservationStatus.CONFIRMED:
                raise ValidationError(
                    "User already has a confirmed reservation for the target event."
                )
            elif existing_reservation.status == ReservationStatus.WAITLISTED:
                raise ValidationError(
                    "User is already on the waitlist for the target event."
                )
            elif existing_reservation.status == ReservationStatus.NO_SHOW:
                raise ValidationError(
                    "User already has a no-show reservation for the target event."
                )
            elif existing_reservation.status == ReservationStatus.CANCELLED:
                raise ValidationError(
                    "User already has a cancelled reservation for the target event."
                )
            else:
                raise ValidationError(
                    f"User already has a reservation of status '{existing_reservation.status}' for the target event."
                )

        if (
            reservation.status
            in [
                ReservationStatus.CONFIRMED,
                ReservationStatus.COMPLETED,
                ReservationStatus.NO_SHOW,
            ]
            and target_event.is_full
        ):
            raise ValidationError("Target event is fully booked.")

        # Check for overlapping reservations (excluding the current one)
        if (
            Reservation.objects.filter(
                user=reservation.user,
                event__start_datetime__lt=target_event.end_datetime,
                event__end_datetime__gt=target_event.start_datetime,
                status__in=[
                    ReservationStatus.CONFIRMED,
                    ReservationStatus.COMPLETED,
                    ReservationStatus.NO_SHOW,
                ],
            )
            .exclude(id=reservation.id)
            .exists()
        ):
            raise ValidationError(
                "User already has a reservation for another event at that time."
            )

        # Validate subscription access to target event service
        if reservation.subscription:
            if not reservation.subscription.service.can_access_service(
                target_event.service,
                skip_credit_validation=skip_credit_validation,
                skip_active_check=skip_active_check,
            ):
                raise ValidationError(
                    f"User's subscription doesn't provide access to '{target_event.service.name}' "
                    "or has no credits remaining."
                )

    def perform(self, target_event) -> "Reservation":
        reservation = self.service.reservation

        with transaction.atomic():
            original_event = reservation.event
            original_subscription = reservation.subscription

            reservation.event = target_event
            reservation.save(update_fields=["event"])

            # Handle subscription credit adjustments for cross-service moves
            if original_subscription:
                if original_event.service != target_event.service:
                    original_subscription.service.restore_credit(original_event.service)

                    credit_used = original_subscription.service.use_credit(
                        target_event.service
                    )
                    if not credit_used:
                        reservation.event = original_event
                        reservation.save(update_fields=["event"])
                        raise ValidationError(
                            f"No credits available in subscription for '{target_event.service.name}'."
                        )

        return reservation

    def execute(
        self,
        target_event_id: str,
        skip_credit_validation: bool = False,
        skip_active_check: bool = False,
    ) -> "Reservation":
        from phoxtail.booking.events.models import Event

        try:
            target_event = Event.objects.get(uuid=target_event_id)
        except Event.DoesNotExist:
            raise ValidationError("Target event not found.")

        reservation = self.service.reservation

        if reservation.subscription:
            skip_credit_validation = True
            skip_active_check = False

        self.authorize()
        self.validate(
            target_event,
            skip_credit_validation=skip_credit_validation,
            skip_active_check=skip_active_check,
        )
        return self.perform(target_event)
