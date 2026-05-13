"""
Admin domain operation for reservation confirmation.
"""

from typing import TYPE_CHECKING, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from phoxtail.booking.subscriptions.constants import SubscriptionStatus

from ....constants import ReservationStatus

if TYPE_CHECKING:
    from phoxtail.booking.subscriptions.models import Subscription

    from ....models import Reservation
    from ...base import ReservationService


class ReservationServiceAdminConfirm:
    """
    Admin domain operation for reservation confirmation.
    Handles both waitlisted→confirmed and cancelled→confirmed transitions.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(
        self,
        subscription: Optional["Subscription"] = None,
        skip_credit_validation: bool = False,
        skip_active_check: bool = False,
    ) -> None:
        from ....models import Reservation

        reservation = self.service.reservation
        event = reservation.event

        # Check if event is in the past
        if event.start_datetime < timezone.now():
            raise ValidationError("This class is no longer available.")

        if event.user_can_access_event(reservation.user) is False:
            raise ValidationError("You do not have the required level to book this class.")

        # Check if event is cancelled
        if event.is_cancelled:
            raise ValidationError("This class has been cancelled and is no longer available.")

        # Check event capacity
        if event.is_full:
            raise ValidationError("This class is fully booked.")

        # Check for overlapping reservations
        if (
            Reservation.objects.filter(
                user=reservation.user,
                event__start_datetime__lt=event.end_datetime,
                event__end_datetime__gt=event.start_datetime,
                status__in=[
                    ReservationStatus.CONFIRMED,
                    ReservationStatus.COMPLETED,
                    ReservationStatus.NO_SHOW,
                ],
            )
            .exclude(id=reservation.id)
            .exists()
        ):
            raise ValidationError("You already have a reservation for another event at that time.")

        # Validate subscription access
        if subscription:
            if not subscription.service.can_access_service(
                event.service,
                skip_credit_validation=skip_credit_validation,
                skip_active_check=skip_active_check,
            ):
                raise ValidationError(
                    f"Your subscription doesn't provide access to '{event.service.name}' "
                    "or you have no credits remaining."
                )

    def _confirm_waitlisted(self, subscription_id: str | None) -> "Reservation":
        from phoxtail.booking.subscriptions.models import Subscription, SubscriptionType

        reservation = self.service.reservation

        if not subscription_id:
            raise ValidationError("Subscription selection is required for waitlisted reservations.")

        with transaction.atomic():
            subscription = Subscription.objects.filter(
                uuid=subscription_id,
                user=reservation.user,
                status=SubscriptionStatus.ACTIVE,
            ).first()

            if not subscription:
                subscription_type = SubscriptionType.objects.filter(uuid=subscription_id, is_active=True).first()
                if not subscription_type:
                    raise ValidationError("Selected subscription is invalid or inactive.")

            self.validate(subscription=subscription)

            reservation.status = ReservationStatus.CONFIRMED
            reservation.subscription = subscription
            reservation.save(update_fields=["status", "subscription"])

            if subscription:
                credit_used = subscription.service.use_credit(reservation.event.service)
                if not credit_used:
                    raise ValidationError(
                        f"No credits available in subscription for '{reservation.event.service.name}'."
                    )

        return reservation

    def _confirm_cancelled(self) -> "Reservation":
        reservation = self.service.reservation

        if not reservation.subscription:
            raise ValidationError("Cancelled reservation must have an associated subscription to be confirmed.")

        with transaction.atomic():
            self.validate(
                subscription=reservation.subscription,
                skip_credit_validation=True,
                skip_active_check=True,
            )

            reservation.status = ReservationStatus.CONFIRMED
            reservation.save(update_fields=["status"])

        return reservation

    def execute(self, subscription_id: str | None = None) -> "Reservation":
        reservation = self.service.reservation

        self.authorize()

        if reservation.status == ReservationStatus.WAITLISTED:
            return self._confirm_waitlisted(subscription_id)
        elif reservation.status in [
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        ]:
            return self._confirm_cancelled()
        else:
            raise ValidationError(f"Cannot confirm booking with status '{reservation.status}'")
