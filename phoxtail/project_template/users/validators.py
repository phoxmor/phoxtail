from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def username_lowercase_validator(value):
    if value != value.lower():
        raise ValidationError("Username must be lowercase.")


def validate_born_at(value):
    if value > timezone.now().date():
        raise ValidationError(_("The birth date cannot be in the future."))
