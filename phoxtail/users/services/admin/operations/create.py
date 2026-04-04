from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from ....services.base import UserService


class UserServiceAdminCreate:
    """Admin domain operation for user creation.

    Orchestrates: user creation + allauth adapter username population
    + allauth EmailAddress record setup.  Validation is handled by the form
    (BaseUserCreationForm provides password matching, password strength,
    and ModelForm's validate_unique provides email uniqueness).
    """

    def __init__(self, service: "UserService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self) -> None:
        pass

    def perform(
        self,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
        request: HttpRequest | None = None,
    ) -> "AbstractUser":
        from allauth.account.adapter import get_adapter
        from allauth.account.utils import setup_user_email

        User = get_user_model()
        adapter = get_adapter(request)

        with transaction.atomic():
            user = User(
                email=User.objects.normalize_email(email),
                first_name=first_name,
                last_name=last_name,
            )

            # Let allauth generate the username properly
            adapter.populate_username(request, user)

            user.set_password(password)
            user.save()

            # Create the allauth EmailAddress record so login/password-reset works
            setup_user_email(request, user, [])

        return user

    def execute(
        self,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
        request: HttpRequest | None = None,
    ) -> "AbstractUser":
        self.authorize()
        self.validate()

        return self.perform(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            request=request,
        )
