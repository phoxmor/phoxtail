# CLI Authentication

This document covers how the Phoxtail CLI and MCP server authenticate against a running Phoxtail project's API. Read [Personal Access Tokens](personal-access-tokens.md) first if you haven't — that document explains the server-side model, hashing, scopes, and lifecycle. This document focuses entirely on the client side: where tokens are stored, how they are resolved, and how they are injected into every HTTP request automatically.

---

## Why credentials need a home

Every `phoxtail studio` command and every MCP tool call reaches the project's Django Ninja API at `/api/streams/v1/`. That API requires a `Bearer` token in the `Authorization` header. Before this system existed, there was no way to supply one — the HTTP clients sent no auth header at all, meaning the API had to be left open or every call would return `401`.

The solution is a credential store (`~/.phoxtail/credentials`) plus a resolver that finds the right token for a given host and attaches it to every outbound request, without the caller having to think about it.

---

## The credential store

Tokens are stored in a TOML file at `~/.phoxtail/credentials`. The directory is created on first write with `chmod 700`; the file is written with `chmod 600`. No other local user can read it.

```toml
# ~/.phoxtail/credentials

["localhost"]
token = "phxt_..."

["studio.example.com"]
token = "phxt_..."

["localhost:8000"]
token = "phxt_..."
```

The key for each entry is the `host[:port]` component of the project's API URL, lowercased. Port numbers are included when non-default so that two projects running on the same machine on different ports each get their own credential entry. `http://` and `https://` schemes are stripped — only the host key is stored.

The format is intentionally minimal. Each entry has exactly one field: `token`. Future fields (e.g. `scopes`, `expires_at`) can be added without breaking existing readers.

### What the key comes from

The host key is derived from `[studio] api_url` in the project's `phoxtail.toml`. Hatched projects ship with `api_url = "http://localhost"` in the generated `phoxtail.toml` (matching the default compose publish of `80:80`). If no URL is configured, or if the CLI is run outside a project, `localhost` is used as the fallback. This means:

- Developers working on a local project (`api_url = "http://localhost"`) store credentials under `localhost`.
- Designers working against a staging server (`api_url = "https://staging.example.com"`) store credentials under `staging.example.com`.
- A developer running two local projects on different ports (`localhost:8080` and `localhost:9000`) gets separate entries automatically.

No manual key management required — the host is always derived from the project config.

### Running several local projects in parallel

Two Phoxtail projects on the same machine cannot share port 80, so parallel setups already need distinct published ports in each `docker-compose.yaml`. The matching rule for credentials is simple: **whatever port you expose, put it in `api_url`**.

```toml
# project A — phoxtail.toml
[studio]
api_url = "http://localhost:8080"

# project B — phoxtail.toml
[studio]
api_url = "http://localhost:9000"
```

`phoxtail auth login` in project A writes under `localhost:8080`; the same command in project B writes under `localhost:9000`. Neither overwrites the other, and both remain resolvable without re-logging in when you switch directories.

If `api_url` does not reflect the actual published port, everything downstream breaks the same way — not just auth. `phoxtail studio …` and MCP tool calls target `api_url` too, so a mismatch yields connection refused or 404, not just a wrong credential lookup. Keep `api_url` in sync with compose.

---

## The resolver

`phoxtail/cli/utils/credentials.py` implements the shared resolution logic. The resolver reads `~/.phoxtail/credentials` keyed by the host derived from the current project's API URL, and returns `None` when no entry exists — no `Authorization` header is sent and the API returns `401`.

```python
# phoxtail/cli/utils/credentials.py

def resolve_token(base_url: str) -> str | None:
    data = _read_file()
    entry = data.get(host_for_url(base_url))
    if isinstance(entry, dict):
        token = entry.get("token")
        if isinstance(token, str) and token:
            return token
    return None
```

The file is re-read on every call. There is no in-process cache — this keeps the resolver honest in long-running processes (like the MCP server) when the user rotates a token mid-session.

---

## Automatic bearer injection

Both HTTP clients call `resolve_token` before sending any request and attach the result as a `Bearer` header if one is found.

### CLI client (`phoxtail/cli/studio/client.py`)

```python
def request(method, path, *, headers=None, ...):
    final_headers = dict(headers or {})
    if "Authorization" not in final_headers:
        token = resolve_token(_api_base_url())
        if token:
            final_headers["Authorization"] = f"Bearer {token}"
    return httpx.request(method, _url(path), headers=final_headers or None, ...)
```

### MCP client (`phoxtail/mcp/_http.py`)

```python
def request(method, path, *, headers=None, ...):
    final_headers = dict(headers or {})
    if "Authorization" not in final_headers:
        token = resolve_token(api_base_url())
        if token:
            final_headers["Authorization"] = f"Bearer {token}"
    return httpx.request(method, url(path), headers=final_headers or None, ...)
```

Both clients follow the same pattern:

- **Preserve explicit headers.** If a caller already passed `Authorization`, it is not overwritten. This is the correct behaviour for tests and for any future caller that needs to pass a different credential.
- **No header when no token.** If `resolve_token` returns `None`, the `Authorization` key is not added at all. `httpx` does not send an empty header.
- **No error thrown.** The injection is silent. If the API rejects the request with `401`, the CLI client prints a recovery hint and exits; the MCP client propagates the error.

### On 401

The CLI client prints a recovery message when it receives a `401` from the API:

```
Error: Authentication credentials were not provided.
Run phoxtail auth login to store an API token.
```

The MCP client does not print this message — it is expected to surface the HTTP error to the agent.

---

## The `phoxtail auth` commands

The `auth` command group is registered without requiring a `phoxtail.toml` project (it is in `NO_PROJECT_COMMANDS`). This means you can run `phoxtail auth login --host staging.example.com` before cloning a project.

### `phoxtail auth login`

Store a token for the current project's host (or an explicit host).

```
phoxtail auth login [--token <value>] [--host <host>] [--no-verify]
```

- If `--token` is omitted, the value is prompted with `getpass` (no echo).
- The host key defaults to the current project's `api_url` host; use `--host` to override.
- By default, the token is verified against the live API before saving. A `401` response causes the save to be aborted. Other non-`401` errors issue a warning but still save.
- `--no-verify` skips the live check entirely — useful in offline or test environments.

```
$ phoxtail auth login
Phoxtail token for localhost: ••••••••••••••••••••••
Saved token for localhost.
```

```
$ phoxtail auth login --host staging.example.com --token phxt_abc123
Saved token for staging.example.com.
```

### `phoxtail auth status`

Show the current credential state.

```
$ phoxtail auth status
Stored in /home/alice/.phoxtail/credentials:
  localhost: phxt_Xf9d…wOo3
  staging.example.com: phxt_Kb7m…r5Qp
Current project host: localhost
```

Token values are masked: the first 8 characters and the last 4 are shown, the rest are replaced with `…`.

The "Current project host" line is always printed, even when no tokens are stored yet — that is exactly when the user needs to know which host key the next `phoxtail auth login` will write under:

```
$ phoxtail auth status
No tokens stored in /home/alice/.phoxtail/credentials.
Current project host: localhost:8080
```

### `phoxtail auth logout`

Remove the stored token for a host.

```
phoxtail auth logout [--host <host>]
```

This removes the entry from `~/.phoxtail/credentials`.

```
$ phoxtail auth logout
Removed token for localhost.
```

---



## Tutorial: setting up and testing credentials end-to-end

This walkthrough assumes you have a running Phoxtail project (`docker compose up`) and a user account in the Wagtail admin.

### Step 1 — generate a token in the admin

1. Open the Wagtail admin at `/admin/`.
2. Navigate to **Settings → Access Tokens** (or search "access tokens" in the admin search).
3. Click **Add access token**.
4. Fill in a name (e.g. `studio-laptop`), leave scopes as `["*"]`, leave expiry blank.
5. Click **Save**. The raw token (`phxt_…`) is shown once on the confirmation screen.
6. Copy it — you will not see it again.

### Step 2 — store the token

In your project directory:

```
phoxtail auth login
```

Paste the token at the prompt. The CLI verifies it against the API and saves it under `~/.phoxtail/credentials`.

Outside a project (or for a remote host):

```
phoxtail auth login --host staging.example.com
```

### Step 3 — confirm the credential is active

```
phoxtail auth status
```

You should see the host listed with the masked token value and the current project host identified.

### Step 4 — run a CLI command

```
phoxtail studio list blocks
```

The bearer token is injected automatically. If the token is valid, you see the block list. If you see a `401`, run `phoxtail auth status` to confirm a token is stored for the right host.

### Step 5 — test the MCP path

Start the MCP server:

```
phoxtail mcp serve
```

The MCP server resolves the token using the same resolver. Any MCP tool call (e.g. `phoxtail_list_blocks`) attaches the bearer header before reaching the API.

### Step 6 — Using credentials inside a container

The credentials file at `~/.phoxtail/credentials` is mounted read-only into the container at `/home/app/.phoxtail`. Run `phoxtail auth login --host <host>` on the host machine before starting the container, and the token is available to any CLI or MCP tool call inside it without further configuration.

### Step 7 — revoke or rotate

To revoke in the Wagtail admin: open the token record, click **Revoke**. The token immediately stops authenticating.

To rotate from the CLI:

```
phoxtail auth logout                     # remove old file entry
phoxtail auth login                      # store new token
```

---

## Implementation files

| File | Role |
|---|---|
| `phoxtail/cli/utils/config.py` | `get_api_base_url()` — single source of truth for the project's API URL; read by the three callers below so they cannot drift |
| `phoxtail/cli/utils/credentials.py` | Shared resolver — file read/write, host key derivation |
| `phoxtail/cli/auth.py` | `phoxtail auth login/status/logout` command group |
| `phoxtail/cli/studio/client.py` | Studio CLI HTTP client — bearer injection on every request |
| `phoxtail/mcp/_http.py` | MCP HTTP client — same bearer injection pattern |
| `phoxtail/tokens/auth.py` | Server-side: SHA-256 hash lookup, expiry/revoke check |
| `phoxtail/tokens/ninja.py` | Server-side: Ninja `APIKeyHeader` adapter |
| `phoxtail/api/__init__.py` | Wires `PhoxtailTokenAuth` to the `NinjaAPI` instance |

---

## Test coverage

| Test file | What it covers |
|---|---|
| `phoxtail/cli/tests/test_credentials.py` | File read/write, host key derivation, file permissions, malformed file handling |
| `phoxtail/cli/tests/test_http_auth_injection.py` | Bearer injection in the Studio CLI client — explicit header preserved, no header when token absent |
| `phoxtail/cli/tests/test_auth.py` | `phoxtail auth status` — empty state, stored hosts |
| `phoxtail/cli/tests/test_config.py` (`TestApiBaseUrl`) | Shared `get_api_base_url()` — fallback when no `[studio]` section, `api_url` read-through, trailing-slash strip, empty-string fallback |

!!! note "MCP bearer injection"
    The Studio CLI client and MCP client use the same pattern, but the MCP bearer injection path currently has no dedicated integration test. `test_http_auth_injection.py` covers only `phoxtail.cli.studio.client`. The comment in that file directing readers to `test_studio_mcp.py` is incorrect — that file does not contain bearer injection tests. This is a known gap.

---

## Known limitations

- **Non-atomic file writes.** `_write_file` writes the credentials file in one shot without an intermediate temp file. A crash mid-write could leave a truncated file. Malformed files are silently ignored (the `test_malformed_file_is_ignored` test confirms this), so the failure mode is "no token found" rather than "corrupted data blocks startup".
- **`--host` defaults to `http://`** when the value has no scheme. `phoxtail auth login --host studio.example.com` stores the key as `studio.example.com`, which is correct, but the live verification request goes to `http://studio.example.com`. If the server only accepts HTTPS, add the scheme explicitly: `--host https://studio.example.com`.
- **Verification endpoint is Studio-specific.** The `phoxtail auth login` verification hit is `GET /api/streams/v1/blocks/`. This is the Studio API. If the project has the tokens app installed but not the streams API, verification will fail even for a valid token. Use `--no-verify` in that case.
