from functools import cached_property
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from .admin.gateway import UserServiceAdminGateway


class UserService:
    """Service layer for User operations.

    Unlike domain-heavy service layers (subscriptions, events, reservations),
    the User service delegates validation to Django and allauth — they are
    the domain experts for authentication. This service focuses on orchestration:
    atomic user creation + allauth EmailAddress setup + adapter calls.
    """

    def __init__(self, user: Optional["AbstractUser"] = None) -> None:
        self.user = user

    @cached_property
    def admin(self) -> "UserServiceAdminGateway":
        from .admin.gateway import UserServiceAdminGateway

        return UserServiceAdminGateway(self)
