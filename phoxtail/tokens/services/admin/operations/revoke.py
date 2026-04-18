from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from ....models import AccessToken

if TYPE_CHECKING:
    from ...base import AccessTokenService


class AccessTokenServiceAdminRevoke:
    """Admin operation: revoke the bound AccessToken.

    Soft-delete: sets ``revoked_at`` to now() and leaves the row in place
    for audit. Idempotent — revoking an already-revoked token is a no-op
    (the original revocation timestamp is preserved).
    """

    def __init__(self, service: "AccessTokenService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self) -> None:
        if self.service.token is None:
            raise ValueError(
                "AccessTokenServiceAdminRevoke requires a bound token — "
                "initialize AccessTokenService(token) first."
            )

    def perform(self) -> AccessToken:
        token = self.service.token

        with transaction.atomic():
            if token.revoked_at is None:
                now = timezone.now()
                AccessToken.objects.filter(pk=token.pk).update(revoked_at=now)
                token.revoked_at = now

        return token

    def execute(self) -> AccessToken:
        self.authorize()
        self.validate()
        return self.perform()
