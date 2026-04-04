"""
Public domain operation for confirming a waitlisted reservation.
"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from phoxtail.booking.subscriptions.constants import SubscriptionStatus

from ....constants import ReservationStatus
from ...base import ReservationValidator

if TYPE_CHECKING:
    from ....models import Reservation
    from ...base import ReservationService


User = get_user_model()


class ReservationServicePublicConfirmWaitlisted:
    """
    Public domain operation for confirming a waitlisted reservation.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self, user: User, event, subscription) -> None:
        from ....models import Reservation

        # Check if event is in the past
        if event.start_datetime < timezone.now():
            raise ValidationError(_("This class is no longer available."))

        if event.user_can_access_event(user) is False:
            raise ValidationError(
                _("You do not have the required level to book this class.")
            )

        # Check if event is cancelled
        if event.is_cancelled:
            raise ValidationError(
                _("This class has been cancelled and is no longer available.")
            )

        # Check if event is unpublished
        if event.is_unpublished:
            raise ValidationError(_("This class is not available for booking."))

        # Check event capacity
        if event.is_full:
            raise ValidationError(_("This class is fully booked."))

        # Check for overlapping reservations
        if Reservation.objects.filter(
            user=user,
            event__start_datetime__lt=event.end_datetime,
            event__end_datetime__gt=event.start_datetime,
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED],
        ).exists():
            raise ValidationError(
                "You already have a reservation for another event at that time."
            )

        # Validate subscription access
        if subscription:
            if not subscription.service.can_access_service(event.service):
                raise ValidationError(
                    f"Your subscription doesn't provide access to '{event.service.name}' "
                    "or you have no credits remaining."
                )

            # Validate grace period access
            ReservationValidator.validate_grace_period_access(subscription)

    def perform(self, reservation, subscription) -> "Reservation":
        with transaction.atomic():
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

    def execute(
        self,
        user: User,
        reservation_id: str,
        subscription_id: str | None = None,
    ) -> "Reservation":
        from phoxtail.booking.subscriptions.models import Subscription, SubscriptionType

        from ....models import Reservation

        # Get the waitlisted reservation
        try:
            reservation = Reservation.objects.get(
                uuid=reservation_id, user=user, status=ReservationStatus.WAITLISTED
            )
        except Reservation.DoesNotExist:
            raise ValidationError("Waitlisted reservation not found.")

        subscription = None
        if subscription_id:
            subscription = Subscription.objects.filter(
                uuid=subscription_id, user=user, status=SubscriptionStatus.ACTIVE
            ).first()

            if not subscription:
                subscription_type = SubscriptionType.objects.filter(
                    uuid=subscription_id, is_active=True
                ).first()
                if not subscription_type:
                    raise ValidationError(
                        "Selected subscription is invalid or inactive."
                    )

        self.authorize()
        self.validate(user, reservation.event, subscription)
        return self.perform(reservation, subscription)
