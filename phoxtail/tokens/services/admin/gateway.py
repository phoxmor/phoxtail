from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import AccessToken
    from ..base import AccessTokenService


class AccessTokenServiceAdminGateway:
    """Gateway for admin-domain operations on AccessTokens.

    "Admin" here means "issued through an administrative path" — the
    Wagtail snippet, a management command, or any internal call. A future
    `public` gateway would host end-user-initiated flows (e.g. a user
    regenerating their own token from a self-service page).
    """

    def __init__(self, service: "AccessTokenService") -> None:
        self.service = service

    def create(
        self,
        user_id: int,
        name: str,
        scopes: list[str] | None = None,
        unrestricted: bool = False,
        description: str = "",
        expires_at: datetime | None = None,
        token_type: str | None = None,
    ) -> tuple["AccessToken", str]:
        """Create a new AccessToken.

        Returns (instance, raw_token). The raw token is shown to the user
        exactly once — the caller is responsible for surfacing it. It is
        never retrievable again.
        """
        from .operations import AccessTokenServiceAdminCreate

        return AccessTokenServiceAdminCreate(self.service).execute(
            user_id=user_id,
            name=name,
            scopes=scopes,
            unrestricted=unrestricted,
            description=description,
            expires_at=expires_at,
            token_type=token_type,
        )

    def revoke(self) -> "AccessToken":
        """Revoke the bound token. Idempotent: re-revoking is a no-op."""
        from .operations import AccessTokenServiceAdminRevoke

        return AccessTokenServiceAdminRevoke(self.service).execute()
