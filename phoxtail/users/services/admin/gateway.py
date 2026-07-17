from typing import TYPE_CHECKING, Any

from django.http import HttpRequest

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from ..base import UserService


class UserServiceAdminGateway:
    """Gateway to all admin domain operations for users.

    Provides namespaced access to admin-specific operations like create and
    update.
    """

    def __init__(self, service: "UserService") -> None:
        self.service = service

    def create(
        self,
        email: str,
        first_name: str,
        last_name: str,
        password: str | None = None,
        request: HttpRequest | None = None,
        **fields: Any,
    ) -> "AbstractUser":
        """Create a new user with proper allauth EmailAddress setup.

        Without ``password`` the account gets an unusable password (API
        creation). Extra ``fields`` (born_at, gender, country, phone_number,
        is_active, ...) are applied verbatim before validation.
        """
        from .operations import UserServiceAdminCreate

        operation = UserServiceAdminCreate(self.service)

        return operation.execute(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            request=request,
            **fields,
        )

    def update(self, request: HttpRequest | None = None, **data) -> "AbstractUser":
        """Update an existing user, syncing allauth EmailAddress if email changed."""
        from .operations import UserServiceAdminUpdate

        operation = UserServiceAdminUpdate(self.service)

        return operation.execute(request=request, **data)

    def verify_email(self) -> str:
        """Mark the user's email verified in allauth; no email is sent.

        Returns ``"verified"`` or ``"already_verified"``.
        """
        from .operations import UserServiceAdminVerifyEmail

        operation = UserServiceAdminVerifyEmail(self.service)

        return operation.execute()

    def delete(self, acting_user: "AbstractUser | None" = None) -> None:
        """Delete a user permanently (cascades to related records).

        Refuses to delete ``acting_user``'s own account.
        """
        from .operations import UserServiceAdminDelete

        operation = UserServiceAdminDelete(self.service)

        return operation.execute(acting_user=acting_user)
