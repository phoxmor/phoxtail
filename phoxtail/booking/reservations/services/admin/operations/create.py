"""
Admin domain operation for reservation creation.
"""

from typing import TYPE_CHECKING, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from phoxtail.booking.subscriptions.constants import SubscriptionStatus

from ....constants import ReservationStatus
from ...base import ReservationValidator

if TYPE_CHECKING:
    from phoxtail.booking.events.models import Event
    from phoxtail.booking.subscriptions.models import Subscription

    from ....models import Reservation
    from ...base import ReservationService


User = get_user_model()


class ReservationServiceAdminCreate:
    """
    Admin domain operation for reservation creation.
    """

    def __init__(self, service: "ReservationService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(
        self,
        user: User,
        event: "Event",
        subscription: Optional["Subscription"],
        reservation_status: str,
    ) -> None:
        from ....models import Reservation

        if event.user_can_access_event(user) is False:
            raise ValidationError(
                "User does not have the required level to book this class."
            )

        # Check for duplicate reservation
        existing_reservation = Reservation.objects.filter(
            user=user,
            event=event,
        ).first()

        if existing_reservation:
            if existing_reservation.status == ReservationStatus.COMPLETED:
                raise ValidationError("User already attended this event.")
            elif existing_reservation.status == ReservationStatus.CONFIRMED:
                raise ValidationError(
                    "User already has a confirmed reservation for this event."
                )
            elif existing_reservation.status == ReservationStatus.WAITLISTED:
                raise ValidationError("User is already on the waitlist for this event.")
            elif existing_reservation.status == ReservationStatus.CANCELLED:
                raise ValidationError(
                    "User already has a cancelled reservation for this event."
                )

        # Check if event is cancelled
        if event.is_cancelled:
            raise ValidationError(
                "This class has been cancelled and is no longer available."
            )

        # Check event capacity
        if event.is_full and reservation_status in [
            ReservationStatus.CONFIRMED,
            ReservationStatus.COMPLETED,
        ]:
            raise ValidationError("This class is fully booked.")

        # Check for overlapping reservations
        if Reservation.objects.filter(
            user=user,
            event__start_datetime__lt=event.end_datetime,
            event__end_datetime__gt=event.start_datetime,
            status__in=[ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED],
        ).exists():
            raise ValidationError(
                "User already has a reservation for another event at that time."
            )

        # Validate subscription access
        if not subscription.service.is_event_within_subscription_period(
            event.start_datetime
        ):
            raise ValidationError(
                "This event is outside the subscription's valid period."
            )

        if not subscription.service.can_access_service(event.service):
            raise ValidationError(
                f"Selected subscription doesn't provide access to '{event.service.name}' "
                "or has no credits remaining."
            )

        # Validate grace period access
        ReservationValidator.validate_grace_period_access(subscription)

    def perform(
        self,
        user: User,
        event: "Event",
        subscription: "Subscription",
        reservation_status: str,
    ) -> "Reservation":
        from ....models import Reservation

        with transaction.atomic():
            reservation_kwargs = {
                "user": user,
                "event": event,
                "subscription": subscription,
            }

            if reservation_status != ReservationStatus.CONFIRMED:
                reservation_kwargs["status"] = reservation_status

            reservation = Reservation.objects.create(**reservation_kwargs)

            # Deduct credit if subscription is used AND status is not WAITLISTED
            if subscription and reservation_status != ReservationStatus.WAITLISTED:
                credit_used = subscription.service.use_credit(event.service)
                if not credit_used:
                    raise ValidationError(
                        f"No credits available in subscription for '{event.service.name}'."
                    )

        return reservation

    def execute(
        self,
        user_id: str,
        event_id: str,
        subscription_id: str,
        reservation_status: str = ReservationStatus.CONFIRMED,
    ) -> "Reservation":
        from phoxtail.booking.events.models import Event
        from phoxtail.booking.subscriptions.models import Subscription, SubscriptionType

        # Get the user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError("User not found.")

        # Get the event
        try:
            event = Event.objects.get(uuid=event_id)
        except Event.DoesNotExist:
            raise ValidationError("Event not found.")

        subscription = None
        try:
            subscription = Subscription.objects.get(
                uuid=subscription_id, user=user, status=SubscriptionStatus.ACTIVE
            )
        except Subscription.DoesNotExist:
            pass

        if not subscription:
            subscription_type = SubscriptionType.objects.filter(
                uuid=subscription_id, is_active=True
            ).first()
            if not subscription_type:
                raise ValidationError("Selected subscription is invalid or inactive.")

        self.authorize()
        self.validate(user, event, subscription, reservation_status)
        return self.perform(user, event, subscription, reservation_status)
