from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from ....services.base import UserService


class UserServiceAdminUpdate:
    """Admin domain operation for user updates.

    Orchestrates field changes + allauth EmailAddress sync when email changes.
    Validation is handled by the form (ModelForm's validate_unique covers
    email uniqueness).
    """

    def __init__(self, service: "UserService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self, **data) -> None:
        user = self.service.user
        if user.is_superuser and data.get("is_active") is False:
            raise ValidationError(
                _("Superuser accounts cannot be deactivated through this interface.")
            )

    def perform(self, request: HttpRequest | None = None, **data) -> "AbstractUser":
        from allauth.account.adapter import get_adapter
        from allauth.account.models import EmailAddress

        user = self.service.user
        old_email = user.email

        with transaction.atomic():
            for field, value in data.items():
                setattr(user, field, value)

            new_email = data.get("email", old_email)

            if new_email != old_email:
                adapter = get_adapter(request)
                adapter.populate_username(request, user)

                EmailAddress.objects.filter(user=user, email=old_email).update(
                    email=new_email
                )

            user.save()

        return user

    def execute(self, request: HttpRequest | None = None, **data) -> "AbstractUser":
        self.authorize()
        self.validate(**data)

        return self.perform(request=request, **data)
