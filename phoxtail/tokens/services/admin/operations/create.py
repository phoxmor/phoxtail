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
from ....scopes import known_scopes, suggest, unknown_scopes

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
        unrestricted: bool,
        expires_at: datetime | None,
    ) -> None:
        if not name or not name.strip():
            raise ValidationError({"name": "Name is required."})

        # A ceiling and "no ceiling" are mutually exclusive, and neither is
        # a safe default: a token with no scopes could do nothing, and one
        # that silently meant "everything" is how over-broad credentials
        # get issued by accident. Make the caller say which they want.
        if not isinstance(scopes, list):
            raise ValidationError({"scopes": "Scopes must be a list."})
        if unrestricted and scopes:
            raise ValidationError(
                {"scopes": "An unrestricted token cannot also carry scopes — it is already unlimited."}
            )
        if not unrestricted and not scopes:
            raise ValidationError({"scopes": "At least one scope is required, or mark the token unrestricted."})
        if not all(isinstance(s, str) and s for s in scopes):
            raise ValidationError({"scopes": "Scopes must be non-empty strings."})

        # Checked at the door because a scope that matches no permission
        # cannot be noticed later: it stores cleanly, and once enforcement
        # lands the token quietly does less than intended while looking
        # like a permissions problem rather than the typo it is.
        known = known_scopes()
        if unknown := unknown_scopes(scopes, known):
            details = []
            for scope in unknown:
                close = suggest(scope, known)
                details.append(
                    f"{scope!r} (did you mean {', '.join(repr(c) for c in close)}?)" if close else repr(scope)
                )
            raise ValidationError(
                {
                    "scopes": (
                        "Unknown scope: " + "; ".join(details) + ". Scopes are Django permission codenames, e.g. "
                        "'phoxtail_streams.change_blockvariant'."
                    )
                }
            )

        if expires_at is not None and expires_at <= timezone.now():
            raise ValidationError({"expires_at": "Expiry must be in the future."})

    def perform(
        self,
        user,
        name: str,
        description: str,
        scopes: list[str],
        unrestricted: bool,
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
                unrestricted=unrestricted,
                expires_at=expires_at,
            )

        return token, raw_token

    def execute(
        self,
        user_id: int,
        name: str,
        scopes: list[str] | None = None,
        unrestricted: bool = False,
        description: str = "",
        expires_at: datetime | None = None,
        token_type: str | None = None,
    ) -> tuple[AccessToken, str]:
        User = get_user_model()
        user = User.objects.get(pk=user_id)

        # No implicit full access: omitting scopes now fails validation
        # rather than quietly minting an unlimited token.
        resolved_scopes = scopes if scopes is not None else []
        # TextChoices members are plain strings at runtime; without Django
        # stubs a type checker reads the attribute as the (value, label)
        # tuple it was assigned from.
        resolved_type: str = token_type or TokenType.PERSONAL  # type: ignore[assignment]

        self.authorize()
        self.validate(
            name=name,
            scopes=resolved_scopes,
            unrestricted=unrestricted,
            expires_at=expires_at,
        )

        return self.perform(
            user=user,
            name=name,
            description=description,
            scopes=resolved_scopes,
            unrestricted=unrestricted,
            expires_at=expires_at,
            token_type=resolved_type,
        )
