from django import forms
from django.contrib.auth import get_user_model

from phoxtail.booking.events.constants import EventStatus
from phoxtail.booking.events.models import Event
from phoxtail.booking.reservations.constants import ReservationStatus
from phoxtail.booking.subscriptions.models import Subscription
from phoxtail.core.fields import SingleSelectSearchField

User = get_user_model()


class ReservationCreateForm(forms.Form):
    user = SingleSelectSearchField(
        queryset=User.objects.filter(is_active=True),
        required=True,
        help_text="Search for an active user",
    )

    subscription = SingleSelectSearchField(
        queryset=Subscription.objects.none(),
        required=True,
        help_text="Select a subscription with access to this service",
    )

    status = forms.ChoiceField(
        choices=ReservationStatus.choices,
        initial=ReservationStatus.CONFIRMED,
        required=True,
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self._set_subscription_queryset()

    def _set_subscription_queryset(self):
        if not self.is_bound:
            return
        user_id = self.data.get("user")
        if not user_id or not self.event:
            return
        self.fields["subscription"].queryset = (
            Subscription.objects.can_access_service(self.event.service)
            .filter(user_id=user_id)
            .prefetch_related(
                "credit_balances__service",
                "subscription_type__credit_allocations__service",
            )
            .order_by("-start_date")
        )


class ReservationMoveForm(forms.Form):
    target_event = SingleSelectSearchField(
        queryset=Event.objects.none(),
        required=True,
        label="Target Event",
        help_text="Search by event key to find the destination event",
    )

    def __init__(self, *args, reservation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reservation = reservation
        if reservation:
            self.fields["target_event"].queryset = (
                Event.objects.select_related("service", "space", "space__location")
                .filter(status=EventStatus.CONFIRMED)
                .exclude(id=reservation.event_id)
                .order_by("-start_datetime")
            )
