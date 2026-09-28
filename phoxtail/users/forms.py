import babel
from allauth.account.forms import LoginForm as AllauthLoginForm
from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from phonenumber_field.formfields import REGION_CODE_TO_COUNTRY_CODE, PrefixChoiceField, SplitPhoneNumberField

from phoxtail.users.models import Gender

User = get_user_model()


class CustomPrefixChoiceField(PrefixChoiceField):
    """Country prefix whose choices lead with the code: "+30 Greece".

    The prefix sits in a narrow box beside the number, and a native <select>
    cuts its text off rather than shortening it, so the code comes first to
    stay in view; the choices stay in the order of the country names. The
    blank choice is a single dash: the box's label already says what it asks,
    and Django's long dashes would be cut off.
    """

    def __init__(self, *args, **kwargs):
        if kwargs.get("choices") is None:
            locale = babel.Locale(translation.to_locale(translation.get_language() or settings.LANGUAGE_CODE))
            countries = sorted(
                (name, region, code)
                for region, code in REGION_CODE_TO_COUNTRY_CODE.items()
                if (name := locale.territories.get(region))
            )
            kwargs["choices"] = [("", "—")] + [(region, f"+{code} {name}") for name, region, code in countries]
        super().__init__(*args, **kwargs)


class CustomSplitPhoneNumberField(SplitPhoneNumberField):
    """Phone number field with placeholder."""

    prefix_field = CustomPrefixChoiceField

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add placeholder to phone number input
        if len(self.widget.widgets) >= 2:
            self.widget.widgets[1].attrs["placeholder"] = _("Enter phone number")
            self.widget.widgets[1].attrs["type"] = "tel"


class LoginForm(AllauthLoginForm):
    def login(self, *args, **kwargs):
        return super().login(*args, **kwargs)


class SignupForm(AllauthSignupForm):
    first_name = forms.CharField(
        max_length=30,
        label=_("First Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter your first name")}),
    )
    last_name = forms.CharField(
        max_length=30,
        label=_("Last Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter your last name")}),
    )

    gender = forms.ModelChoiceField(
        queryset=Gender.objects.all(),
        label=_("Gender"),
        required=False,
        empty_label=_("Select your gender"),
    )
    born_at = forms.DateField(
        label=_("Date of Birth"),
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )
    country = CountryField(blank_label=_("Select your country")).formfield(label=_("Country"), required=False)
    phone_number = CustomSplitPhoneNumberField(label=_("Phone Number"))

    def save(self, request):
        user = super().save(request)
        user.gender = self.cleaned_data["gender"]
        user.born_at = self.cleaned_data["born_at"]
        user.country = self.cleaned_data["country"]
        user.phone_number = self.cleaned_data["phone_number"]
        user.save()

        return user


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=30,
        label=_("First Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter your first name")}),
    )
    last_name = forms.CharField(
        max_length=30,
        label=_("Last Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter your last name")}),
    )
    # Optional here, unlike signup: the model allows a blank number, so an
    # edit form that cannot clear one would trap whatever is stored.
    phone_number = CustomSplitPhoneNumberField(label=_("Phone Number"), required=False)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "born_at",
            "gender",
            "country",
            "phone_number",
            "avatar",
        ]
        widgets = {
            "born_at": forms.DateInput(attrs={"type": "date"}),
            "avatar": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
