# Personal Access Tokens

Personal Access Tokens (PATs) are the authentication mechanism for machine clients — the CLI, the MCP server, and (in Phase 5) remote Phoxtail projects acting as sync remotes. They sit alongside allauth's account system without overlapping it: allauth owns identity (who you are), PATs own access (what a machine is allowed to do on your behalf).

---

## Why PATs

Every Phoxtail project is a self-contained design environment that will eventually be addressable by other projects, agents, and tools over the network. The [sync vision](../studio/sync.md) describes Project A pulling from Project B, Project B pushing to a registry, and an agency maintaining a canonical collection that client projects subscribe to. None of these flows tolerate interactive login — they are machine-to-machine operations that need a credential they can store, rotate, and revoke independently.

PATs are the right primitive for this because:

- **No password in a config file.** The user logs into the web UI once to generate a token, copies it, and never types their password into a terminal or config file again.
- **Named tokens.** A designer running three machines generates three tokens — `studio-laptop`, `ci-server`, `studio-mcp`. Each has its own name, its own expiry, and can be revoked without touching the others.
- **Scoped access.** A token for a remote sync operation does not need write access to the full API. Scopes bound what each token can do without requiring a separate account per use case.
- **Framework-agnostic.** The core validate-hash-then-return-user logic is plain Python. Swapping Django Ninja for another framework means swapping a ten-line adapter, not the token system itself.

---

## Architecture

### Package position

Tokens live in `phoxtail/tokens/` — a library app at the same level as `phoxtail.core`, `phoxtail.design`, and `phoxtail.streams`. This is the right position because:

- Every Phoxtail project that exposes the API needs the same token model. Centralized fixes propagate via pip.
- The app has its own migrations, model, and service layer — it is not a sub-module of `phoxtail.api` (which has no ORM) or `phoxtail.core` (which contains infrastructure, not domain models).
- It follows `PhoxtailAppConfig` so it auto-wires into any project that adds it to `INSTALLED_APPS`.

```
phoxtail/tokens/
├── apps.py            # PhoxtailAppConfig — auto-wired by wire_apps()
├── models.py          # AccessToken
├── auth.py            # authenticate(raw_token) → User | None
├── ninja.py           # Thin APIKeyHeader adapter (optional)
├── services/
│   ├── __init__.py
│   ├── base.py        # TokenService
│   └── admin/
│       ├── gateway.py
│       └── operations/
│           ├── create.py
│           └── revoke.py
├── admin.py           # Wagtail snippet for token management
└── migrations/
```

### The model

```python
class AccessToken(models.Model):
    class TokenType(models.TextChoices):
        USER_PAT = "user_pat", "Personal Access Token"
        SERVICE   = "service",  "Service Token"
        SYNC      = "sync",     "Sync Remote Token"

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="access_tokens")
    name         = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    token_type   = models.CharField(max_length=20, choices=TokenType.choices, default=TokenType.USER_PAT)
    prefix       = models.CharField(max_length=8, db_index=True)  # "phxt_Xxxx"
    token_last_four = models.CharField(max_length=4)              # display only
    token_hash   = models.CharField(max_length=64, unique=True)   # SHA-256 hex
    scopes       = models.JSONField(default=list)                  # ["*"] or ["api:read", "sync:pull:phoxtail"]
    expires_at   = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
```

### The authentication function

`auth.py` is the framework-agnostic core. It is plain Python — no Ninja, no DRF, no framework import.

```python
import hashlib
import hmac
from django.utils import timezone

def authenticate(raw_token: str) -> "User | None":
    """Return the user for a valid raw token, or None."""
    if not raw_token or len(raw_token) < 8:
        return None

    prefix = raw_token[:8]
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    try:
        token = AccessToken.objects.select_related("user").get(
            prefix=prefix,
            token_hash=token_hash,
            revoked_at__isnull=True,
        )
    except AccessToken.DoesNotExist:
        return None

    if token.expires_at and token.expires_at < timezone.now():
        return None

    AccessToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
    return token.user
```

Two implementation details matter here:

1. **Prefix narrows the lookup.** The database filters on the indexed `prefix` column before comparing the hash. Without the prefix, authentication would require scanning the entire `token_hash` column or using a hash-indexed lookup — the prefix makes the query O(1) with a standard B-tree index.
2. **No timing leak.** The `get()` raises `DoesNotExist` on miss rather than returning a row, so there is no value to compare in constant time. If you later move to a scheme that does a lookup-then-compare, use `hmac.compare_digest`, not `==`.

### The Ninja adapter

`ninja.py` is the only file that imports from `ninja`. Everything else in the package is framework-free.

```python
from ninja.security import APIKeyHeader
from .auth import authenticate

class PhoxtailTokenAuth(APIKeyHeader):
    param_name = "Authorization"

    def authenticate(self, request, key):
        if key and key.startswith("Bearer "):
            return authenticate(key[7:])
        return None
```

Wire it to the API instance:

```python
# phoxtail/api/__init__.py
from phoxtail.tokens.ninja import PhoxtailTokenAuth

api = NinjaAPI(
    auth=PhoxtailTokenAuth(),
    ...
)
```

If Phoxtail migrates away from Ninja, this ten-line adapter is the only thing that changes. The model, the service layer, and the hash logic remain untouched.

---

## Token format

A raw token has four parts:

```
phxt_Xf9dK2mNqR7vBcJwYtLsP4uAeGhZiOo
└──┘ └────────────────────────────────┘
 prefix (8 chars)    body (32 chars, URL-safe base64 from 24 random bytes)
```

| Segment | Length | Purpose |
|---|---|---|
| `phxt_` | 5 chars | Human identifier — "this is a Phoxtail token" |
| 3 random chars | 3 chars | Combined with the literal prefix = 8-char indexed `prefix` field |
| body | 32 chars | 192 bits of entropy from `secrets.token_urlsafe(24)` |

**Storing:**
- `prefix`: first 8 characters of the raw token — stored in plaintext, indexed, used to narrow DB lookup
- `token_last_four`: last 4 characters — stored in plaintext, displayed in the admin so users can identify tokens
- `token_hash`: `hashlib.sha256(raw_token.encode()).hexdigest()` — the only secret stored

**Raw token shown once.** The `create` operation returns `(AccessToken instance, raw_token_string)`. The caller (view, CLI command, API response) is responsible for showing it to the user exactly once. It is never retrievable after that moment. This is what GitHub, Linear, and every other serious token issuer does.

---

## Scopes

The `scopes` field is a JSON array of strings that bounds what a token is permitted to do. It is part of the model from day one because adding it later requires a painful data migration and a vocabulary retrofit.

### Vocabulary

| Scope | Meaning |
|---|---|
| `*` | Full access — default for user PATs |
| `api:read` | GET requests to any API endpoint |
| `api:write` | POST / PUT / PATCH / DELETE to any API endpoint |
| `sync:pull:<namespace>` | Pull variants from the given namespace (Phase 5) |
| `sync:push:<namespace>` | Push variants to the given namespace (Phase 5) |

### Enforcement

On Day 1, the Ninja auth adapter does not enforce scopes — it only checks that the token is valid. Scope enforcement is a **middleware or per-endpoint decorator** added in a later phase once the vocabulary is established. The field must exist now so that:

- Tokens created today already carry scope metadata.
- Phase 5 can enforce `sync:push:<namespace>` without a migration or a back-fill.

!!! note "Default scope"
    User PATs created via the admin UI default to `["*"]`. Service tokens created programmatically (e.g. for a CI pipeline) should be issued with the minimum required scopes.

---

## Storage and security

### Hashing

SHA-256 is the right choice here. bcrypt, argon2, and scrypt are designed for slow hashing of low-entropy passwords. Token bodies have 192 bits of entropy — brute-forcing a SHA-256 hash of a 192-bit random value is computationally infeasible. Fast hashing means authentication adds microseconds of latency, not milliseconds.

### The "raw token never stored" invariant

The `AccessToken` model has no `token` field. The raw token is a local variable inside the `create` operation. After `create()` returns, the only representation of the secret in the system is the SHA-256 hash. This means:

- A full database dump does not expose any usable tokens.
- There is no API endpoint that returns a previously-created token.
- There is no admin action that reveals a token after creation.

### Token rotation

Rotation in this system means: revoke the old token, create a new one, update the client's stored credential. There is no in-place "rotate" that preserves the token identity, because preserving identity would require storing the raw token to re-issue it.

```
TokenService(old_token).admin.revoke()
new_token_instance, raw = TokenService().admin.create(user=user, name=..., scopes=...)
```

This is documented explicitly so callers do not expect a single atomic rotation endpoint.

---

## Lifecycle

```
created ──► active ──► [expires] ──► expired (rejected silently)
                 └──► [revoked] ──► revoked (rejected silently)
```

### Create

The `create` operation generates a token and returns the raw string exactly once:

```python
instance, raw_token = TokenService().admin.create(
    user_id=user.pk,
    name="studio-laptop",
    scopes=["*"],
    expires_at=None,  # never expires
)
# Show raw_token to the user. It will never be retrievable again.
```

### Use

Every authenticated API request carries `Authorization: Bearer <raw_token>`. The `authenticate()` function resolves it to a user in a single indexed DB query and updates `last_used_at`.

### Revoke

Revocation is a soft-delete — `revoked_at` is set to `now()`. The token record is preserved for audit purposes. The token immediately stops authenticating.

```python
TokenService(token).admin.revoke()
```

### Expiry

If `expires_at` is set, `authenticate()` rejects the token silently after that timestamp. The token record is preserved. Expired tokens are visible in the admin with their expiry date so users understand why they stopped working.

---

## Integration

### CLI

The CLI reads the token from the environment or from a credentials file. The recommended convention mirrors git's credential storage:

```toml
# ~/.phoxtail/credentials (chmod 600)
[myproject.example.com]
token = "phxt_..."
```

CLI commands that call the API inject the token as a `Bearer` header via the shared HTTP client in `phoxtail/mcp/_http.py` (or the analogous CLI client).

### MCP server

The MCP server's `_http.py` reads the token from the environment:

```python
import os
headers = {"Authorization": f"Bearer {os.environ['PHOXTAIL_API_TOKEN']}"}
```

The `phoxtail mcp serve` command exports this automatically when the user has configured credentials.

### Future: OAuth2 for external agents

PATs cover the case where **you** are accessing **your own** project. When a **third-party agent** (Claude.ai, another tool) wants to access your project on your behalf, the right protocol is OAuth2. The MCP spec defines an OAuth2-based authorization flow for exactly this scenario.

OAuth2 is additive — it is a separate authorization server layer that sits above the same `phoxtail/tokens/` infrastructure. An OAuth2 authorization grant ultimately produces an `AccessToken` row with a `token_type` of `service` and a scoped `scopes` value. The validation path is identical: `Authorization: Bearer`, `authenticate()`, user resolved. The difference is in how the token came to exist — PAT (user-generated) vs OAuth2 grant (agent-authorized).

This means the PAT model you build today is directly reused in the OAuth2 phase. No migration, no parallel token table.

---

## What this is not

- **Not session authentication.** allauth handles browser-based login, CSRF, session cookies, email verification, and MFA. Do not use PATs in browser contexts. Do not use session cookies in machine contexts.
- **Not user identity.** allauth owns the concept of "who a user is." PATs only answer "is this machine allowed to act as user X."
- **Not an OAuth2 authorization server.** PATs are user-generated credentials. OAuth2 delegation (third parties acting on behalf of users) is a separate layer described in the [Future](#future-oauth2-for-external-agents) section above.
- **Not per-endpoint permission control.** Django's permission system and `phoxtail.core.permissions` govern what a user may do within the application. Scopes govern what a token may do on behalf of a user. Scopes narrow permissions — they cannot expand them.

---

## Token management UI

Until the `dashboard/` scaffold ships (deferred to v1.0.0 per the package vision), token management lives in the **Wagtail admin** as a snippet:

- List view: name, type, last four digits, scopes, last used, created, status (active / expired / revoked)
- Create action: name, description, type, scopes, expiry date — returns the raw token on a one-time confirmation screen
- Revoke action: sets `revoked_at` immediately

This is intentionally minimal. The target user (developer-designer) already works in the Wagtail admin. A dedicated token portal is a UI enhancement, not a requirement.

---

## Future work

| Feature | Phase | Notes |
|---|---|---|
| Scope enforcement in middleware | Next | Gate endpoints by required scope |
| `sync:pull/push:<namespace>` scopes | Phase 5 | Used by sync remote authentication |
| IP allowlist per token | Later | `allowed_ips: JSONField` — useful for CI tokens |
| OAuth2 authorization server | Phase 5+ | `django-oauth-toolkit` on top of this model |
| Token portal in `dashboard/` scaffold | v1.0.0 | Replaces the Wagtail snippet for end users |
| Webhook signatures | Later | HMAC-signed payloads for event delivery |

---

## Service layer reference

Tokens follow the [service layer pattern](service-layer-overview.md). The closest reference implementation is the [Users service](service-layer-users.md) — minimal `validate()` because the framework (here: `secrets` + `hashlib`) does the hard work, and the service focuses on orchestration.

Key operations:

| Operation | Class | Gateway |
|---|---|---|
| Create a token | `TokenServiceAdminCreate` | `admin` |
| Revoke a token | `TokenServiceAdminRevoke` | `admin` |

`rotate` is documented as a two-step caller responsibility (revoke then create), not a single operation, because there is no atomic single-step rotation that preserves the raw token secret.
