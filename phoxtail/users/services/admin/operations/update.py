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
    ``full_clean()`` enforces model rules (email uniqueness, phone/country
    formats, birth-date validity) regardless of the caller — forms validate
    earlier too, API callers rely on this pass alone.
    """

    def __init__(self, service: "UserService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self, **data) -> None:
        user = self.service.user
        assert user is not None, "operation requires a service bound to a user"
        if user.is_superuser and data.get("is_active") is False:
            raise ValidationError(_("Superuser accounts cannot be deactivated through this interface."))

    def perform(self, request: HttpRequest | None = None, **data) -> "AbstractUser":
        from allauth.account.adapter import get_adapter
        from allauth.account.models import EmailAddress

        user = self.service.user
        assert user is not None, "operation requires a service bound to a user"
        old_email = user.email
        adapter = get_adapter(request)

        if "email" in data:
            # Mirror the create path — otherwise case-variant domains slip
            # past the unique check and produce near-duplicate accounts.
            data["email"] = type(user).objects.normalize_email(data["email"])
        if "username" in data:
            # allauth's own validation; shallow skips the uniqueness lookup,
            # which would match the user being updated — the model's unique
            # constraint still guards via full_clean().
            data["username"] = adapter.clean_username(data["username"], shallow=True)

        with transaction.atomic():
            for field, value in data.items():
                setattr(user, field, value)

            user.full_clean()

            new_email = data.get("email", old_email)

            if new_email != old_email:
                adapter.populate_username(request, user)

                EmailAddress.objects.filter(user=user, email=old_email).update(email=new_email)

            user.save()

        return user

    def execute(self, request: HttpRequest | None = None, **data) -> "AbstractUser":
        self.authorize()
        self.validate(**data)

        return self.perform(request=request, **data)
