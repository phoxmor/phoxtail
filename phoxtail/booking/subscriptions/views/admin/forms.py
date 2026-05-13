from django import forms
from django.contrib.auth import get_user_model

from phoxtail.booking.subscriptions.models import SubscriptionType
from phoxtail.core.fields import SingleSelectSearchField

User = get_user_model()


class SubscriptionCreateForm(forms.Form):
    user = SingleSelectSearchField(
        queryset=User.objects.filter(is_active=True),
        required=True,
        help_text="Search for an active user",
    )

    subscription_type = SingleSelectSearchField(
        queryset=SubscriptionType.objects.select_related("location").filter(is_active=True).order_by("name"),
        required=True,
        help_text="Select a subscription type",
    )
