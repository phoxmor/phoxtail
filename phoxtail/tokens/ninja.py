"""django-ninja adapter for AccessToken authentication.

This is the **only** file in `phoxtail.tokens` that imports from ninja.
If Phoxtail migrates to a different HTTP framework, replacing this
adapter is the full extent of the change — the hashing, lookup, and
lifecycle logic in `auth.py` remain identical.
"""

from __future__ import annotations

from ninja.security import APIKeyHeader

from .auth import authenticate

_BEARER_PREFIX = "Bearer "


class PhoxtailTokenAuth(APIKeyHeader):
    """Resolve an ``Authorization: Bearer <raw_token>`` header to a User.

    Ninja treats the returned value as ``request.auth``. We return the
    ``User`` instance so endpoints can read ``request.auth`` directly
    rather than having to re-fetch it. Returning ``None`` makes ninja
    respond with 401.
    """

    param_name = "Authorization"

    def authenticate(self, request, key):
        if not key or not key.startswith(_BEARER_PREFIX):
            return None
        raw_token = key[len(_BEARER_PREFIX) :]
        return authenticate(raw_token)
