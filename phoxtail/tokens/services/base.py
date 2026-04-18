from functools import cached_property
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..models import AccessToken
    from .admin.gateway import AccessTokenServiceAdminGateway


class AccessTokenService:
    """Service layer for AccessToken operations.

    Like the Users service, this one is orchestration-heavy and
    validation-light: the hashing and random-bytes generation are provided
    by the stdlib (`secrets`, `hashlib`), so the service focuses on
    assembling the parts and enforcing invariants the model alone cannot
    express (non-empty scopes, future-dated expiries, idempotent revoke).
    """

    def __init__(self, token: Optional["AccessToken"] = None) -> None:
        self.token = token

    @cached_property
    def admin(self) -> "AccessTokenServiceAdminGateway":
        from .admin.gateway import AccessTokenServiceAdminGateway

        return AccessTokenServiceAdminGateway(self)
