from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from ....services.base import UserService


class UserServiceAdminCreate:
    """Admin domain operation for user creation.

    Orchestrates: user creation + allauth adapter username population
    + allauth EmailAddress record setup.  Form-driven callers pass a
    validated ``password``; API-driven callers omit it and the account is
    created with an unusable password (no login access until a separate
    activation flow grants it).  No email is ever sent from here —
    ``setup_user_email`` only creates the ``EmailAddress`` record.

    ``full_clean()`` enforces model rules (email uniqueness, phone/country
    formats, birth-date validity) and raises ``ValidationError`` for the
    shared API instance to translate into a 422.
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
        password: str | None = None,
        request: HttpRequest | None = None,
        **fields: Any,
    ) -> "AbstractUser":
        from allauth.account.adapter import get_adapter
        from allauth.account.utils import setup_user_email

        User = get_user_model()
        adapter = get_adapter(request)
        username = fields.pop("username", None)

        with transaction.atomic():
            user = User(
                email=User.objects.normalize_email(email),
                first_name=first_name,
                last_name=last_name,
                **fields,
            )

            if username:
                # allauth's own validation: configured validators, blacklist,
                # case-insensitive uniqueness.
                user.username = adapter.clean_username(username)

            # Let allauth generate the username when none was supplied
            adapter.populate_username(request, user)

            if password is None:
                user.set_unusable_password()
            else:
                user.set_password(password)

            user.full_clean()
            user.save()

            # Create the allauth EmailAddress record so login/password-reset works
            setup_user_email(request, user, [])

        return user

    def execute(
        self,
        email: str,
        first_name: str,
        last_name: str,
        password: str | None = None,
        request: HttpRequest | None = None,
        **fields: Any,
    ) -> "AbstractUser":
        self.authorize()
        self.validate()

        return self.perform(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            request=request,
            **fields,
        )
