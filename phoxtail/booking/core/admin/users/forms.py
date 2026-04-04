from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import BaseUserCreationForm

from phoxtail.booking.core.models import BookingGroup
from phoxtail.users.models import Gender

User = get_user_model()


class BookingGroupsMixin:
    """Adds a booking_groups checkbox field to user forms."""

    def _init_booking_groups(self, user=None):
        self.fields["booking_groups"] = forms.ModelMultipleChoiceField(
            queryset=BookingGroup.objects.filter(is_active=True).order_by("name"),
            required=False,
            label="Booking Groups",
            widget=forms.CheckboxSelectMultiple,
        )
        if user is not None:
            self.initial["booking_groups"] = user.booking_groups.values_list(
                "pk", flat=True
            )


class UserUpdateForm(BookingGroupsMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "username",
            "is_active",
            "born_at",
            "gender",
            "country",
            "phone_number",
        ]
        widgets = {
            "born_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].disabled = True
        self.fields["username"].disabled = True
        self.fields["gender"].queryset = Gender.objects.all()
        self.fields["gender"].required = True
        self.fields["born_at"].required = True
        self.fields["country"].required = True
        self.fields["phone_number"].required = True
        self._init_booking_groups(user=self.instance)

        if self.instance and self.instance.is_superuser:
            del self.fields["is_active"]


class UserCreateForm(BookingGroupsMixin, BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self._init_booking_groups()
