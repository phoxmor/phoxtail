from typing import TYPE_CHECKING

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
        password: str,
        request: HttpRequest | None = None,
    ) -> "AbstractUser":
        """Create a new user with proper allauth EmailAddress setup."""
        from .operations import UserServiceAdminCreate

        operation = UserServiceAdminCreate(self.service)

        return operation.execute(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            request=request,
        )

    def update(self, request: HttpRequest | None = None, **data) -> "AbstractUser":
        """Update an existing user, syncing allauth EmailAddress if email changed."""
        from .operations import UserServiceAdminUpdate

        operation = UserServiceAdminUpdate(self.service)

        return operation.execute(request=request, **data)
