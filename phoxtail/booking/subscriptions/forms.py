from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from .models import Subscription, SubscriptionCreditBalance


class SubscriptionCreditBalanceForm(forms.ModelForm):
    """
    Form for editing individual credit balances.
    """

    class Meta:
        model = SubscriptionCreditBalance
        fields = ["service", "credits"]


# Create the formset - manages multiple credit balance forms together
SubscriptionCreditBalanceFormSet = inlineformset_factory(
    parent_model=Subscription,
    model=SubscriptionCreditBalance,
    form=SubscriptionCreditBalanceForm,
    extra=0,  # No empty forms
    can_delete=False,
    can_order=False,
)


class SubscriptionUpdateForm(forms.ModelForm):
    """
    Form for updating subscriptions in the admin billing interface.
    """

    class Meta:
        model = Subscription
        fields = [
            "start_date",
            "end_date",
            "status",
            "credits",
            "is_paid",
            "unpaid_reservation_limit",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "status": forms.RadioSelect,
        }

    def clean(self):
        """
        Perform cross-field validation.
        """
        cleaned_data = super().clean()

        # Validate that end_date is after start_date
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", _("End date must be after start date."))

        return cleaned_data
