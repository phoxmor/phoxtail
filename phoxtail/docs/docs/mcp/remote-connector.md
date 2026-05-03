# MCP Remote Connector

## Purpose

The local `phoxtail mcp serve` (stdio) command works well for a single developer using Claude Code in the project root. It does not work for a team: other admins cannot install phoxtail locally, Claude.ai's web interface cannot spawn subprocesses, and API-based workflows cannot reach a subprocess that lives inside a terminal session.

This document defines the target architecture for exposing the Phoxtail MCP server as a **remote HTTP connector** accessible from Claude.ai's web interface, the Claude API, and any future MCP-compatible client. It records every design decision and their rationale, and it is the authoritative implementation guide for the agent or engineer who builds this.

The goal is a working connector that an admin can add to their Claude.ai account at `https://domain.com/mcp/`, authenticate with their own credentials, and immediately use all Phoxtail tools — exactly as they work today in Claude Code, but from any device, without local setup.

No phased approach. No intermediate architectures. This document describes the end state and the steps to reach it.

---

## Known blocker — Claude.ai web Bearer token bug

**Before investing engineering time on this, verify that the following bug is resolved.**

As of May 2026, Claude.ai's web interface completes the OAuth flow (DCR → authorize → token exchange) but never attaches the `Authorization: Bearer` header to subsequent MCP requests. The server issues a valid token, Claude.ai stores it, then makes MCP requests without it — resulting in an infinite 401 → refresh loop. The bug is confirmed, tracked in multiple open issues (anthropics/claude-code#46140, anthropics/claude-ai-mcp#155, #79, #136), and has no workaround for the web interface.

**Claude Code CLI is not affected.** The same server works correctly from `claude mcp add` with HTTP transport. If the target audience is exclusively Claude Code users (not the claude.ai web interface), this is not a blocker.

Check the issue tracker before starting Step 3. If still open, the connector cannot be used from claude.ai web until Anthropic fixes it.

---

## Architecture overview

```
Admin browser
    │
    │  1. Add connector → enters https://domain.com/mcp/
    ▼
Claude.ai
    │
    │  2. Discovers auth server via /.well-known/oauth-protected-resource
    │  3. Self-registers via DCR POST /register
    │  4. OAuth 2.1 (authorization code + PKCE) — admin logs in, approves scopes
    ▼
Django: /authorize/  →  admin logs in  →  approves scopes
    │
    │  5. DOT issues access token bound to (admin_user, resource=mcp_url)
    ▼
Claude.ai stores token
    │
    │  6. Authorization: Bearer <dot_token>
    ▼
nginx  →  /mcp/  →  FastMCP HTTP server (port 8001)
    │
    │  7. Token introspection: POST /oauth/introspect/
    ▼
Django  →  validates token  →  returns (user, scopes)
    │
    │  8. Tool executes: Authorization: Bearer <dot_token>
    ▼
Django API (/api/content/v1/, /api/streams/v1/, ...)
    │
    │  9. Django validates same token via DOT  →  acts as that admin
    ▼
ORM  →  Database
```

Each admin authenticates with their own credentials. Every tool call is issued as that admin. Django sees the same user identity for both the introspection call and the downstream API call. The audit trail is per-admin, not per-service-account.

---

## What we know about Claude.ai's OAuth behavior

These are confirmed facts, not assumptions. They replace the "Day 1 verification" section of the original document.

**Claude.ai is a public client.** It does not hold a `client_secret`. It uses PKCE (Proof Key for Code Exchange) as its only proof of identity. Any `CLIENT_CONFIDENTIAL` or `client_secret` configuration is wrong.

**Claude.ai uses Dynamic Client Registration (DCR, RFC 7591).** When a user adds a remote connector URL, Claude.ai POSTs its own metadata to your `/register` endpoint and receives a `client_id` back. There is no fixed, pre-known `client_id`. Pre-registration does not apply.

**The discovery and authorization sequence is fixed:**
1. `GET /.well-known/oauth-protected-resource` — finds the authorization server URL
2. `GET /.well-known/oauth-authorization-server` — fetches auth server metadata (authorize/token/register endpoints)
3. `POST /register` — DCR: Claude.ai registers itself, receives `client_id`
4. `GET /authorize?client_id=...&code_challenge=...` — user logs in and approves scopes
5. `POST /token` — exchanges authorization code for access token
6. All subsequent MCP requests: `Authorization: Bearer <token>`

**Known Claude.ai endpoint path quirk:** Claude.ai has been observed ignoring `authorization_endpoint` and `token_endpoint` values from the metadata document, instead hardcoding `/authorize`, `/token`, and `/register` relative to the resource base URL. This means DOT's default paths (`/oauth/authorize/`, `/oauth/token/`) must be aliased or rewritten at the root. Verify this is still true when you test — it may be fixed in a later Claude.ai release.

**Confirmed redirect URIs:**
- `https://claude.ai/api/mcp/auth_callback`
- `https://claude.com/api/mcp/auth_callback`

Register both. The exact URI Claude.ai sends will be one of these; register both to be safe.

**Tokens must be bound to a resource (RFC 8707).** Claude.ai sends a `resource` parameter in the token request identifying the MCP server URL. DOT must validate and bind the token to that resource. A token issued for one MCP server cannot be replayed against another.

---

## Committed decisions

These are not options to evaluate. They are the architecture. Each one is explained once.

### 1. Separate FastMCP process, not embedded in Django

The FastMCP HTTP server runs as an independent process on port 8001, not mounted inside Django's ASGI application. Nginx proxies `/mcp/` to it.

The reason is the existing architecture: every MCP tool issues `httpx` requests against the Django API. Embedding the MCP server inside Django ASGI would create a server calling itself over HTTP — possible but circular and harder to reason about. Keeping the MCP server separate preserves the clean boundary that has already proven correct: `Agent → MCP tool → HTTP → API endpoint → ORM`.

This also means the MCP server can be restarted independently of Django (e.g. after a phoxtail package upgrade) without dropping web traffic.

### 2. django-oauth-toolkit for the OAuth 2.1 authorization server

`django-oauth-toolkit` (DOT) provides the OAuth 2.1 authorization server endpoints: `/oauth/authorize/`, `/oauth/token/`, `/oauth/introspect/`, and the metadata discovery endpoint. DOT supports PKCE natively, which is mandatory per the MCP authorization spec.

The Django project already has `django-allauth` for user login. The two libraries do not conflict: allauth handles the login form that appears inside the DOT `/oauth/authorize/` flow. The user authenticates via allauth, then DOT issues the token. They operate at different layers of the same flow.

### 3. Parallel token systems — DOT and phoxtail/tokens coexist

DOT manages OAuth-issued tokens (Claude.ai, future connectors). `phoxtail/tokens` continues managing personal access tokens (CLI use, scripts, `phoxtail mcp serve` via stdio).

The Django API's Ninja auth backends are extended to accept both. Ninja's `auth=` parameter accepts a list; the first backend that returns a user wins:

```python
@router.get("/variants/", auth=[PhoxtailTokenAuth(), DotTokenAuth()])
```

This is a small Django-side change and it means existing personal tokens continue to work everywhere without modification. Consolidating the two token systems is a future refactor, not an MVP concern.

### 4. Multi-user: every admin acts as themselves

The `phoxtail.mcp._http` module currently calls `resolve_token(api_base_url())` — a single token read from local config. Under the HTTP transport, this must change: the incoming OAuth token is forwarded directly to the Django API.

The MCP server extracts the `Authorization: Bearer <token>` header from the incoming MCP request and forwards it on every outbound `httpx` call to the Django API. The Django API validates it via DOT and acts as the authenticated user. There is no shared service account.

The concrete change in `_http.py` is that `request()` accepts an optional `auth_token` argument that overrides `resolve_token()`. FastMCP's tool context provides the incoming request headers, from which the token is extracted.

### 5. Sessions tools excluded from the HTTP transport

`phoxtail_studio_open_variant` writes template files to the MCP server's local filesystem and returns file paths for the agent to edit. Over an HTTP transport, the agent (running on Claude.ai's infrastructure) cannot open those paths. The tool is meaningless in this context.

The sessions module is excluded from the HTTP build via a transport check in `_register_core_tools()`:

```python
def _register_core_tools(transport: str = "stdio") -> None:
    import phoxtail.mcp.content.body
    import phoxtail.mcp.content.pages
    # ... other modules always registered ...

    if transport == "stdio":
        import phoxtail.mcp.studio.sessions  # filesystem-dependent
```

The `phoxtail mcp http` command passes `transport="http"` to `_register_tools()`. The stdio command continues to pass `transport="stdio"` and registers sessions normally.

### 6. Scope vocabulary — committed

Scopes follow the pattern `{domain}:{action}`. The `AccessToken.scopes` JSONField already stores them; the `phoxtail/tokens` model's comment explicitly anticipates this ("scope vocabulary is not enforced yet; the field exists so tokens created today already carry scope metadata once enforcement lands").

| Scope | Permits |
|---|---|
| `studio:read` | list/get blocks, variants, collections, shared blocks, context |
| `studio:write` | create/update blocks, variants, collections, shared blocks |
| `content:read` | list/get pages, locales, page types, internal links |
| `content:write` | create/update pages, internal links, body |
| `content:publish` | publish and unpublish pages |
| `media:read` | list/get images, documents, videos, audio |
| `media:write` | upload/update/delete media |

Claude.ai is registered (via DCR) with all seven scopes. The user is shown the scope list at the OAuth consent screen and approves them once.

Scope enforcement in tool functions uses a FastMCP dependency that reads scopes from the introspected token and raises `403` if the required scope is absent. Each tool decorator declares its required scope. Scope enforcement also lives in the Django API's dual-auth backend — a token with only `studio:read` cannot reach a `content:publish` endpoint even if it bypasses the MCP layer.

### 7. `_touch_reload` is a no-op in production

`phoxtail/mcp/_http.py:28` calls `trigger.touch()` after successful writes to cause Django's autoreloader to pick up changes during local development. In production there is no autoreloader running. The touch either does nothing (file doesn't exist) or writes a timestamp to a watched file that no one is watching. It does not need to be removed — it is already guarded by `if trigger.exists()`. This is documented here so the next engineer does not spend time on it.

---

## Why not use `fastmcp-personal-auth`?

[`fastmcp-personal-auth`](https://github.com/crumrine/fastmcp-personal-auth) is a working FastMCP OAuth 2.1 + DCR implementation confirmed to work with Claude.ai. It is worth reading its source for reference. However it is not directly usable here because it is designed for a fundamentally different model:

- It authenticates **clients** (Claude.ai the app), not **users** (the human admin). It has no concept of individual users. Every token grants access to all tools, for a single implicit owner.
- It stores state in JSON files on disk, not in a database.
- It has no extension points to plug in an external identity provider like Django/DOT.

Phoxtail's connector needs per-user identity: Alice's token must call the API as Alice and Bob's token as Bob. `fastmcp-personal-auth` cannot do this. Its DCR and PKCE handling code is worth reading as a reference implementation; it should not be imported as a dependency.

---

## Components

### FastMCP HTTP server (`phoxtail mcp http`)

A new subcommand in `phoxtail/cli/mcp.py`:

```python
@app.command("http")
def http_serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8001, help="Bind port."),
) -> None:
    """Start the MCP HTTP server for remote connector use.

    Intended to be run as a system service (systemd, Docker) behind nginx.
    Authentication is handled via OAuth 2.1 — callers must present a valid
    DOT-issued Bearer token acquired through the authorization code flow.
    """
    from phoxtail.mcp import mcp_server, _register_tools

    _register_tools(transport="http")
    sys.stderr.write(f"Phoxtail MCP HTTP server starting on {host}:{port}...\n")
    mcp_server.run(transport="streamable-http", host=host, port=port)
```

The server runs with `streamable-http` transport, which is the current MCP standard for remote servers. SSE (`sse`) is being deprecated and should not be used.

### OAuth 2.1 authorization server (django-oauth-toolkit)

Install: `django-oauth-toolkit>=3.0` (v3 added proper OAuth 2.1 and PKCE support).

Add to `INSTALLED_APPS` and wire the URL conf:

```python
# urls.py
path("oauth/", include("oauth2_provider.urls", namespace="oauth2_provider")),
```

Configure `OAUTH2_PROVIDER` settings:

```python
# settings.py
OAUTH2_PROVIDER = {
    "SCOPES": {
        "studio:read": "Read studio resources (blocks, variants, collections)",
        "studio:write": "Create and update studio resources",
        "content:read": "Read pages and content",
        "content:write": "Create and update pages",
        "content:publish": "Publish and unpublish pages",
        "media:read": "Read media library",
        "media:write": "Upload and manage media",
    },
    "PKCE_REQUIRED": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
    # Enable RFC 8707 resource indicators — tokens are bound to the MCP server URL
    "RESOURCE_SERVER_INTROSPECTION_URL": None,  # using local introspection, not remote
}
```

### Dynamic Client Registration (DCR) endpoint

Claude.ai does not use a pre-registered `client_id`. It self-registers on first use by POSTing to `/register`. DOT does not ship a DCR endpoint; add one:

```python
# phoxtail/oauth/views.py
import json, secrets
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from oauth2_provider.models import Application

@method_decorator(csrf_exempt, name="dispatch")
class DynamicClientRegistrationView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_request"}, status=400)

        redirect_uris = data.get("redirect_uris", [])
        allowed = {"https://claude.ai/api/mcp/auth_callback", "https://claude.com/api/mcp/auth_callback"}
        if not all(uri in allowed for uri in redirect_uris):
            return JsonResponse({"error": "invalid_redirect_uri"}, status=400)

        app = Application.objects.create(
            name=data.get("client_name", "MCP Client"),
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            client_id=secrets.token_urlsafe(32),
            redirect_uris=" ".join(redirect_uris),
        )

        return JsonResponse({
            "client_id": app.client_id,
            "client_name": app.name,
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code"],
            "token_endpoint_auth_method": "none",  # public client
        }, status=201)
```

Wire at the root so Claude.ai's endpoint assumption holds:

```python
# urls.py — add alongside the existing oauth/ include
path("register", DynamicClientRegistrationView.as_view()),
path("authorize", RedirectView.as_view(url="/oauth/authorize/", query_string=True)),
path("token", RedirectView.as_view(url="/oauth/token/", query_string=True)),
```

### Well-known discovery documents

Two documents are required. Both are served by Django (or nginx as static files).

**`/.well-known/oauth-protected-resource`** — tells Claude.ai where the authorization server lives:

```json
{
  "resource": "https://domain.com/mcp/",
  "authorization_servers": ["https://domain.com/"],
  "bearer_methods_supported": ["header"],
  "scopes_supported": ["studio:read", "studio:write", "content:read", "content:write", "content:publish", "media:read", "media:write"]
}
```

**`/.well-known/oauth-authorization-server`** — tells Claude.ai the exact auth endpoints (RFC 8414). DOT exposes this automatically once configured; verify it includes the `registration_endpoint` pointing to `/register`.

### Token validation in the MCP server

The MCP server validates incoming tokens by calling Django's DOT introspection endpoint before executing any tool:

```
POST /oauth/introspect/
Authorization: Basic <mcp_server_client_credentials>
Body: token=<incoming_bearer_token>
```

DOT returns `{"active": true, "username": "...", "scope": "studio:read studio:write ..."}` for a valid token. The MCP server caches this per-request (not across requests — tokens can be revoked).

A FastMCP middleware performs this check and attaches the result to the request context. Each tool reads the authenticated user and their scopes from this context. The middleware also validates the `Origin` header on every request (required by the streamable-http spec to prevent DNS rebinding attacks).

### Token forwarding to the Django API

In `_http.py`, the `request()` function is modified to accept the OAuth token extracted from the incoming MCP request:

```python
def request(
    method: str,
    path: str,
    *,
    auth_token: str | None = None,   # new: OAuth token from MCP caller
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    final_headers = dict(headers or {})
    if "Authorization" not in final_headers:
        token = auth_token or resolve_token(api_base_url())
        if token:
            final_headers["Authorization"] = f"Bearer {token}"
    ...
```

Under the HTTP transport, `auth_token` is always provided from the FastMCP request context. Under stdio, it falls back to `resolve_token()` exactly as today.

### Dual auth in the Django API

DOT provides `oauth2_provider.contrib.rest_framework.OAuth2Authentication` for DRF. For Ninja, a thin adapter is needed. Do not do a raw `AccessToken.objects.get(token=raw)` lookup — recent versions of DOT hash tokens at rest. Use DOT's own validation path:

```python
# phoxtail/tokens/ninja.py (extend existing file)
from oauth2_provider.backends import OAuth2Backend

class DotOAuthTokenAuth(APIKeyHeader):
    param_name = "Authorization"

    def authenticate(self, request, key):
        if not key or not key.startswith("Bearer "):
            return None
        # Delegate to DOT's own validator — handles hashed tokens correctly
        backend = OAuth2Backend()
        user = backend.authenticate(request=request)
        return user  # None if invalid
```

API routers that the MCP server calls accept both backends:

```python
auth=[PhoxtailTokenAuth(), DotOAuthTokenAuth()]
```

Personal tokens from `phoxtail/tokens` continue to work for the CLI and stdio server. OAuth tokens from DOT work for the HTTP connector. The same Django API serves both without modification to any endpoint logic.

---

## Deployment

### nginx configuration

The MCP server speaks plain HTTP on `127.0.0.1:8001`. Nginx terminates TLS and proxies.

```nginx
# Add inside the existing server {} block for domain.com

location /mcp/ {
    proxy_pass         http://127.0.0.1:8001;
    proxy_http_version 1.1;

    # Required for streamable-http (SSE-style streaming connections)
    proxy_buffering    off;
    proxy_cache        off;
    proxy_read_timeout 3600s;

    # Standard proxy headers
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;

    # Required for SSE keepalive
    proxy_set_header   Connection        "";
}
```

`proxy_buffering off` and a long `proxy_read_timeout` are not optional. Without them, streaming responses are buffered and held until the connection closes, which breaks the MCP streaming protocol. This is the most common silent failure when deploying FastMCP behind nginx.

### systemd service

```ini
[Unit]
Description=Phoxtail MCP HTTP Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/project
EnvironmentFile=/path/to/project/.env
ExecStart=/path/to/.venv/bin/phoxtail mcp http --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Restart the service after any phoxtail package upgrade. The Django application server does not need to restart.

---

## Implementation plan

The following steps are ordered by dependency. An agent or engineer picks up from step 0 and works down. Each step is independently testable before moving to the next.

**Step 0 — Verify the Claude.ai Bearer token bug is resolved**

Check anthropics/claude-code#46140 and anthropics/claude-ai-mcp#155. If either is still open and unresolved, the connector cannot be used from the claude.ai web interface. Stop here and wait for the fix, or proceed with Claude Code CLI as the target client instead.

If targeting Claude Code CLI only, the OAuth flow is still required but the Bearer token bug does not apply — CLI correctly sends the token.

---

**Step 1 — `phoxtail mcp http` command**

In `phoxtail/cli/mcp.py`, add the `http` subcommand as shown above. In `phoxtail/mcp/__init__.py`, thread the `transport` argument through `_register_core_tools()` and gate the sessions import. Verify that `phoxtail mcp http` starts without error and that the studio/content tools are listed by an MCP inspector, but sessions tools are absent.

---

**Step 2 — nginx proxy + root path aliases**

Add the nginx `location /mcp/` block to the existing server config. Also add root-level aliases for the OAuth endpoints that Claude.ai expects at `/authorize`, `/token`, and `/register` (see the URL conf additions in the Components section above). Confirm that `curl https://domain.com/mcp/` reaches the FastMCP server.

---

**Step 3 — django-oauth-toolkit setup**

Install DOT. Add it to `INSTALLED_APPS`. Run migrations. Add the URL conf. Configure `OAUTH2_PROVIDER` settings with the scope vocabulary and `PKCE_REQUIRED`. Verify that `https://domain.com/.well-known/oauth-authorization-server` returns valid metadata including a `registration_endpoint`.

---

**Step 4 — DCR endpoint**

Implement the `DynamicClientRegistrationView` shown above and wire it to `/register`. Test by POSTing a client registration payload manually:

```bash
curl -X POST https://domain.com/register \
  -H "Content-Type: application/json" \
  -d '{"client_name":"test","redirect_uris":["https://claude.ai/api/mcp/auth_callback"],"grant_types":["authorization_code"]}'
```

Confirm a `client_id` is returned and an `Application` row exists in the database.

---

**Step 5 — Well-known discovery documents**

Serve `/.well-known/oauth-protected-resource` from Django or as a static file via nginx. Verify DOT is already serving `/.well-known/oauth-authorization-server` and that the `registration_endpoint` field in that document points to `/register`.

---

**Steps 6 + 7 + 8 — Token validation, forwarding, and dual auth** (one functional unit)

These three steps are implemented together — nothing is testable until all three are done.

**6.** Add FastMCP middleware that extracts `Authorization: Bearer <token>`, calls `/oauth/introspect/`, validates the response, validates the `Origin` header, and attaches `(user, scopes)` to the request context. Return `401` on any failure.

**7.** Modify `_http.py`'s `request()` to accept and forward `auth_token`. Update tool functions to extract the token from the FastMCP request context and pass it through.

**8.** Add `DotOAuthTokenAuth` to `phoxtail/tokens/ninja.py` and add it to the `auth=[...]` list on API routers the MCP tools call.

Verify end-to-end: obtain a DOT token manually via the authorization flow, make a tool call with it, confirm Django logs show the correct username.

---

**Step 9 — Scope enforcement**

Define a FastMCP dependency factory `require_scope("studio:read")` that reads scopes from the request context and raises `403` if absent. Apply to every tool function. Also add scope checks to the `DotOAuthTokenAuth` backend on the Django API side — a token with only `studio:read` must be rejected at the API level too, not only at the MCP middleware level.

Verify by testing a token with partial scopes against both the MCP server and the Django API directly.

---

**Step 10 — End-to-end test**

Add the connector in Claude.ai (or Claude Code CLI). Complete the OAuth flow. Invoke a tool — for example, "list all variants in the hero block." Confirm the response is correct and that Django's request log shows the authenticated admin's username.

---

## `TokenType.OAUTH`

The `phoxtail/tokens/constants.py` `TokenType` class already notes that `oauth` will be added when there is a concrete caller. Add it now:

```python
class TokenType(models.TextChoices):
    PERSONAL = "personal", _("Personal")
    OAUTH    = "oauth",    _("OAuth (connector-issued)")
```

This type is not used for the DOT tokens themselves (those are managed by DOT's own model), but it is used if a future flow issues a `phoxtail/tokens` AccessToken as the *result* of an OAuth exchange — for example, an OAuth-to-personal-token bridge that lets external systems obtain a scoped personal token via OAuth without ongoing DOT dependency. This is a future concern; add the constant now so tokens created during testing already carry the right type.

---

## What the Sessions tools need long-term

The sessions workflow (`open_variant` → edit files → `commit_variant`) is excluded from the HTTP transport because it writes to the MCP server's local filesystem. This is not a permanent limitation — it is a design mismatch.

The long-term resolution is to replace local file storage with server-side draft storage: `open_variant` writes to a database-backed draft (a new model in `phoxtail/streams/`) and returns the draft content directly in the response. `commit_variant` reads from the same draft. The agent edits content in-memory rather than via filesystem tools.

This is not part of the connector MVP. It is recorded here so the decision is visible: sessions tools are not abandoned, they are awaiting a different storage backend. The transport check in `_register_core_tools()` is the placeholder.

---

## Relationship to `architecture.md`

`architecture.md` describes the MCP server as a stdio server started by local MCP clients. The architecture described in this document is additive: the same `FastMCP` instance, the same tool registrations, the same `_http.py` HTTP client — run with a different transport and fronted by an authorization layer.

The stdio path remains unchanged and continues to be the right choice for local development with Claude Code. A developer working locally does not need OAuth, does not need nginx, and does not need DOT. They run `phoxtail mcp serve` and it works as always. The HTTP path is additive infrastructure for team and web use.

The only code changes that touch the stdio path are: the `transport` argument threading through `_register_core_tools()`, and the `auth_token` parameter on `_http.request()` (which defaults to `resolve_token()` — no behavioral change for stdio callers).
