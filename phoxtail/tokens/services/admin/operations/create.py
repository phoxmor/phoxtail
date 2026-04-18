import hashlib
import secrets
import string
from datetime import datetime
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ....constants import TokenType
from ....models import AccessToken

if TYPE_CHECKING:
    from ...base import AccessTokenService


# Alphabet for the 3 random characters that sit between "phxt_" and the
# body. URL-safe and unambiguous — avoids the base64 padding character.
_PREFIX_ALPHABET = string.ascii_letters + string.digits

# Bytes of entropy for the token body. secrets.token_urlsafe(n) returns a
# base64-url-encoded string whose length is ceil(n * 4 / 3). 24 bytes →
# 32 characters → 192 bits of entropy, well beyond any brute-force reach.
_BODY_ENTROPY_BYTES = 24


def _generate_raw_token() -> str:
    """Return a freshly-minted raw token string.

    Format: ``phxt_`` + 3 random chars + 32-char URL-safe body.
    Total length: 40 chars.
    """
    random_prefix = "".join(secrets.choice(_PREFIX_ALPHABET) for _ in range(3))
    body = secrets.token_urlsafe(_BODY_ENTROPY_BYTES)
    return f"phxt_{random_prefix}{body}"


class AccessTokenServiceAdminCreate:
    """Admin operation: create a new AccessToken.

    The service generates the raw token, hashes it, and persists the hash
    plus its display-only parts (prefix, suffix). The raw token string is
    returned once from ``execute`` and never stored.
    """

    def __init__(self, service: "AccessTokenService") -> None:
        self.service = service

    def authorize(self) -> None:
        # Hook for future RBAC. "Admin" in the gateway name refers to the
        # issuance path, not a permission check — the caller (Wagtail view,
        # management command) is expected to have gated this already.
        pass

    def validate(
        self,
        name: str,
        scopes: list[str],
        expires_at: datetime | None,
    ) -> None:
        if not name or not name.strip():
            raise ValidationError({"name": "Name is required."})

        if not isinstance(scopes, list) or not scopes:
            # Empty scopes would be a footgun: the token exists but can do
            # nothing. "*" is the explicit wildcard; callers must opt in.
            raise ValidationError(
                {"scopes": "At least one scope is required. Use ['*'] for full access."}
            )
        if not all(isinstance(s, str) and s for s in scopes):
            raise ValidationError({"scopes": "Scopes must be non-empty strings."})

        if expires_at is not None and expires_at <= timezone.now():
            raise ValidationError({"expires_at": "Expiry must be in the future."})

    def perform(
        self,
        user,
        name: str,
        description: str,
        scopes: list[str],
        expires_at: datetime | None,
        token_type: str,
    ) -> tuple[AccessToken, str]:
        raw_token = _generate_raw_token()
        digest = hashlib.sha256(raw_token.encode()).hexdigest()

        with transaction.atomic():
            token = AccessToken.objects.create(
                user=user,
                name=name.strip(),
                description=description,
                token_type=token_type,
                prefix=raw_token[:8],
                suffix=raw_token[-4:],
                digest=digest,
                scopes=scopes,
                expires_at=expires_at,
            )

        return token, raw_token

    def execute(
        self,
        user_id: int,
        name: str,
        scopes: list[str] | None = None,
        description: str = "",
        expires_at: datetime | None = None,
        token_type: str | None = None,
    ) -> tuple[AccessToken, str]:
        User = get_user_model()
        user = User.objects.get(pk=user_id)

        resolved_scopes = scopes if scopes is not None else ["*"]
        resolved_type = token_type or TokenType.PERSONAL

        self.authorize()
        self.validate(name=name, scopes=resolved_scopes, expires_at=expires_at)

        return self.perform(
            user=user,
            name=name,
            description=description,
            scopes=resolved_scopes,
            expires_at=expires_at,
            token_type=resolved_type,
        )
