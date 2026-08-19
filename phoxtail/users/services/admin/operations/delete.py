from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from ....services.base import UserService


class UserServiceAdminDelete:
    """Admin domain operation for user deletion.

    Deletion is irreversible: installed apps may reference users with
    ``on_delete=CASCADE``, so related records (and the allauth EmailAddress
    rows) are removed with the account. Deactivation is the softer
    alternative. Superusers are deletable — except the acting account
    itself, mirroring the Wagtail admin rule.
    """

    def __init__(self, service: "UserService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self, acting_user: "AbstractUser | None" = None) -> None:
        user = self.service.user
        assert user is not None, "operation requires a service bound to a user"
        if acting_user is not None and user.pk == acting_user.pk:
            raise ValidationError(_("You cannot delete your own account."))

    def perform(self) -> None:
        user = self.service.user
        assert user is not None, "operation requires a service bound to a user"
        user.delete()

    def execute(self, acting_user: "AbstractUser | None" = None) -> None:
        self.authorize()
        self.validate(acting_user=acting_user)

        return self.perform()
