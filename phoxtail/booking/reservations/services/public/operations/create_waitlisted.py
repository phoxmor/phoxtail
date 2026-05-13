"""
Public domain operation for waitlisted reservation creation.
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


class ReservationServicePublicCreateWaitlisted:
    """
    Public domain operation for creating a waitlisted reservation.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self, user: User, event, subscription) -> None:
        from ....models import Reservation

        # Check if event is in the past
        if event.start_datetime < timezone.now():
            raise ValidationError("This class is no longer available.")

        if event.user_can_access_event(user) is False:
            raise ValidationError("You do not have the required level to book this class.")

        # Check for any existing reservation
        existing_reservation = Reservation.objects.filter(
            user=user,
            event=event,
        ).first()

        if existing_reservation:
            if existing_reservation.status == ReservationStatus.COMPLETED:
                raise ValidationError("User already attended the target event.")
            elif existing_reservation.status == ReservationStatus.CONFIRMED:
                raise ValidationError("User already has a confirmed reservation for the target event.")
            elif existing_reservation.status == ReservationStatus.WAITLISTED:
                raise ValidationError("User is already on the waitlist for the target event.")
            elif existing_reservation.status == ReservationStatus.CANCELLED:
                raise ValidationError("User already has a cancelled reservation for the target event.")
            else:
                raise ValidationError(
                    f"User already has a reservation of status '{existing_reservation.status}' for the target event."
                )

        # Check if event is cancelled
        if event.is_cancelled:
            raise ValidationError(_("This class has been cancelled and is no longer available."))

        # Check if event is unpublished
        if event.is_unpublished:
            raise ValidationError(_("This class is not available for booking."))

        # For waitlisted reservations, the event must actually be full
        if not event.is_full:
            raise ValidationError(_("This class still has available spots. Please make a normal booking instead."))

        # Check for overlapping reservations
        if Reservation.objects.filter(
            user=user,
            event__start_datetime__lt=event.end_datetime,
            event__end_datetime__gt=event.start_datetime,
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED],
        ).exists():
            raise ValidationError("You already have a reservation for another event at that time.")

        # Validate subscription access
        if subscription:
            if not subscription.service.can_access_service(event.service):
                raise ValidationError(
                    f"Your subscription doesn't provide access to '{event.service.name}' "
                    "or you have no credits remaining."
                )

            # Validate grace period access
            ReservationValidator.validate_grace_period_access(subscription)

    def perform(self, user: User, event, subscription) -> "Reservation":
        from ....models import Reservation

        with transaction.atomic():
            if not subscription:
                raise ValidationError("No valid subscription found. Please purchase a subscription first.")

            reservation = Reservation.objects.create(
                user=user,
                event=event,
                status=ReservationStatus.WAITLISTED,
                subscription=subscription,
            )

        return reservation

    def execute(
        self,
        user: User,
        event_id: str,
        subscription_id: str,
    ) -> "Reservation":
        from phoxtail.booking.events.models import Event
        from phoxtail.booking.subscriptions.models import Subscription, SubscriptionType

        try:
            event = Event.objects.get(uuid=event_id)
        except Event.DoesNotExist:
            raise ValidationError("Event not found.")

        subscription = Subscription.objects.filter(
            uuid=subscription_id, user=user, status=SubscriptionStatus.ACTIVE
        ).first()

        if not subscription:
            subscription_type = SubscriptionType.objects.filter(uuid=subscription_id, is_active=True).first()
            if not subscription_type:
                raise ValidationError("Selected subscription is invalid or inactive.")

        self.authorize()
        self.validate(user, event, subscription)
        return self.perform(user, event, subscription)
