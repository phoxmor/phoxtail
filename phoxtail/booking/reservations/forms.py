from django import forms

from .constants import ReservationStatus
from .models import Reservation
from .services import ReservationService


class ReservationUpdateForm(forms.ModelForm):
    """
    Form for updating reservation status and notes.
    Routes status transitions to the appropriate service class.
    All statuses are shown — the service layer validates whether
    a given transition is allowed.
    """

    status = forms.ChoiceField(
        choices=ReservationStatus.choices,
        widget=forms.RadioSelect,
        required=True,
    )

    class Meta:
        model = Reservation
        fields = ["status", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reservation_deleted = False
        # Capture original status before ModelForm._post_clean() overwrites instance
        self._original_status = self.instance.status

    def save(self, user=None, commit=True):
        new_status = self.cleaned_data["status"]
        notes = self.cleaned_data.get("notes", "")

        # Refresh instance from DB since ModelForm._post_clean() overwrites fields
        self.instance.refresh_from_db()

        # Always update notes
        if self.instance.notes != notes:
            self.instance.notes = notes
            self.instance.save(update_fields=["notes"])

        # No status transition — notes-only update
        if new_status == self._original_status:
            return self.instance

        svc = ReservationService(self.instance)

        # Route to appropriate service
        if new_status == ReservationStatus.CANCELLED:
            svc.admin.cancel(user=user)
            # cancel may delete the reservation
            self.reservation_deleted = not Reservation.objects.filter(id=self.instance.id).exists()
            return self.instance

        if new_status == ReservationStatus.CONFIRMED:
            subscription_id = str(self.instance.subscription.uuid) if self.instance.subscription.uuid else None
            return svc.admin.confirm(subscription_id=subscription_id)

        if new_status == ReservationStatus.COMPLETED:
            return svc.admin.complete()

        if new_status == ReservationStatus.NO_SHOW:
            return svc.admin.mark_no_show()

        if new_status == ReservationStatus.WAITLISTED:
            return svc.admin.revert_to_waitlisted()

        return self.instance
