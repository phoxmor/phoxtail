# Chatbot Providers and Models

The Phoxtail chatbot is designed to support multiple AI providers and models — including
self-hosted open-source models running locally — without requiring code changes between
deployments. This document describes the target architecture, the data models, the admin
surface, and the migration path from the current env-var-only setup.

---

## Why a database-driven provider system

The simplest possible setup is two env vars: `GEMINI_API_KEY` and `PHOXTAIL_CHATBOT_MODEL`.
That works for a single cloud provider with a static config. It breaks down in two real
scenarios:

**Per-model permission gating.** You may want basic users to access a fast, cheap model
and power users to access a larger, more capable one. There is no way to express that with
env vars — it requires a model record with a `required_permission` field that the chat
endpoint checks against `request.user`.

**Self-hosted models.** A local Ollama instance, a vLLM deployment, or any
OpenAI-compatible endpoint has a fundamentally different shape than a cloud API: it needs a
`base_url` (e.g. `http://localhost:11434/v1`), may need no API key at all, and uses the
OpenAI wire protocol regardless of what model is actually running. That cannot be collapsed
into `PROVIDER=google` + `MODEL=llama3`. It needs a provider record with a `provider_type`,
an optional `base_url`, and an optional API key reference.

PydanticAI already supports this via `OpenAIModel(base_url="...", api_key="unused")` for
any OpenAI-compatible endpoint. The architecture described here builds the admin surface
around what PydanticAI can already do.

---

## Data models

Two models. One owns the connection; the other names what to run on it.

### `AIProvider`

One row per connection target. Examples: Google Gemini cloud, a local Ollama instance,
a company-internal vLLM deployment.

```python
class AIProvider(models.Model):
    class ProviderType(models.TextChoices):
        GOOGLE    = "google",    "Google (Gemini)"
        OPENAI    = "openai",    "OpenAI"
        OPENAI_COMPATIBLE = "openai_compatible", "OpenAI-compatible (Ollama, vLLM, …)"
        ANTHROPIC = "anthropic", "Anthropic (Claude)"

    identifier      = models.SlugField(unique=True)        # e.g. "google-gemini", "local-ollama"
    display_name    = models.CharField(max_length=100)
    provider_type   = models.CharField(max_length=32, choices=ProviderType.choices)
    base_url        = models.URLField(blank=True)           # required for openai_compatible
    api_key_env_var = models.CharField(max_length=200, blank=True)
    #   ^ stores the *name* of the env var, not the key itself.
    #   e.g. "GEMINI_API_KEY" or "OPENAI_API_KEY". Blank for local/unauthenticated providers.
    is_active       = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_name"]
```

**The env-var-name pattern.** The API key never enters the database. The provider record
stores the *name* of the environment variable the operator has set on the server
(e.g. `"GEMINI_API_KEY"`). At runtime, `get_agent()` resolves it:

```python
api_key = os.environ.get(provider.api_key_env_var) if provider.api_key_env_var else None
```

This keeps secrets in the environment — out of DB dumps, backups, and admin audit logs —
while letting the admin configure which env var each provider uses without a deploy.

For self-hosted providers with no authentication, leave `api_key_env_var` blank. The
OpenAI-compatible client will send `"nokey"` or an equivalent dummy value if the endpoint
requires a non-empty header but ignores its contents.

### `AIModel`

One row per model that operators want to expose to users. Multiple models can share one
provider.

```python
class AIModel(models.Model):
    provider            = models.ForeignKey(AIProvider, on_delete=models.CASCADE,
                                            related_name="models")
    identifier          = models.CharField(max_length=200)
    # ^ the model name the API accepts, e.g. "gemini-2.5-flash", "llama3.2", "gpt-4o"
    display_name        = models.CharField(max_length=100)
    required_permission = models.ForeignKey(
        "auth.Permission", null=True, blank=True, on_delete=models.SET_NULL
    )
    # ^ if set, the user must hold this permission to select this model.
    # null = available to all users who can access the chatbot.
    is_active           = models.BooleanField(default=True)
    sort_order          = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "display_name"]
        unique_together = [["provider", "identifier"]]
```

---

## Per-turn model switching

The correct UX pattern — matching Claude.ai, Gemini, and most modern chat interfaces — is
that the model can be changed on any turn, not just at conversation start. The model is a
property of the *request*, not the *conversation*.

```python
class StreamRequest(Schema):
    message: str
    conversation_uuid: str | None = None
    model_id: int | None = None
    # ^ pk of the AIModel to use for this turn.
    # None = use the system default (first active model by sort_order).
```

`Conversation` stores `last_model_used` as a UI hint only — so the frontend can
pre-select the same model on the next turn as a convenience. It does not constrain which
model the next request uses.

```python
class Conversation(models.Model):
    ...
    last_model_used = models.ForeignKey(
        "AIModel", null=True, blank=True, on_delete=models.SET_NULL
    )
```

---

## Permission gating per model

In `chat_stream`, after resolving the requested model, check `required_permission`:

```python
model = AIModel.objects.get(pk=payload.model_id, is_active=True)
if model.required_permission:
    perm = f"{model.required_permission.content_type.app_label}.{model.required_permission.codename}"
    if not user.has_perm(perm):
        raise HttpError(403, "You do not have access to this model.")
```

This composes naturally with the `access_chatbot` gate that runs before it: a user must
first pass the coarse-grained chatbot permission, then the fine-grained model permission.

---

## Agent factory refactor

Today `get_agent()` returns a process-wide singleton. With multiple providers and models,
it becomes a keyed cache:

```python
# phoxtail/agent/llm.py
# Note: constructor signatures below should be verified against the installed
# PydanticAI version when implementing — the API surface evolves quickly.

from __future__ import annotations
import os
from functools import lru_cache
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIModel
from .tools import get_tools

@lru_cache(maxsize=16)
def get_agent(provider_type: str, model_identifier: str,
              base_url: str | None, api_key_env_var: str | None) -> Agent:
    api_key = os.environ.get(api_key_env_var) if api_key_env_var else None

    if provider_type == "google":
        model = GoogleModel(model_identifier, api_key=api_key)
    elif provider_type in ("openai", "openai_compatible"):
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        model = OpenAIModel(model_identifier, **kwargs)
    else:
        raise ValueError(f"Unsupported provider type: {provider_type!r}")

    return Agent(model=model, tools=get_tools())
```

The `lru_cache` key is the four arguments — so one `Agent` instance is created per
`(provider_type, model_identifier, base_url, api_key_env_var)` combination and reused
across requests. Cache invalidation (e.g. after a key rotation) requires a process restart;
this is acceptable for MVP and should be documented to operators.

At the call site in `chat_stream`:

```python
agent = get_agent(
    provider_type=ai_model.provider.provider_type,
    model_identifier=ai_model.identifier,
    base_url=ai_model.provider.base_url or None,
    api_key_env_var=ai_model.provider.api_key_env_var or None,
)
```

---

## Bootstrap: env-var fallback

Until `AIProvider` and `AIModel` rows exist in the database, `chat_stream` falls back to
the legacy env vars:

```python
def _resolve_model(model_id: int | None) -> AIModel | None:
    if model_id is not None:
        return AIModel.objects.filter(pk=model_id, is_active=True).first()
    return AIModel.objects.filter(is_active=True).order_by("sort_order").first()


def _legacy_get_agent() -> Agent:
    """Fallback used when no AIModel rows exist. Reads env vars directly."""
    model_name = os.environ.get("PHOXTAIL_CHATBOT_MODEL", "gemini-2.5-flash")
    return get_agent(
        provider_type="google",
        model_identifier=model_name,
        base_url=None,
        api_key_env_var="GEMINI_API_KEY",
    )
```

In `chat_stream`:

```python
ai_model = _resolve_model(payload.model_id)
agent = get_agent(...) if ai_model else _legacy_get_agent()
```

**Deprecation timeline:** The fallback and the env vars `PHOXTAIL_CHATBOT_MODEL` and
`GEMINI_API_KEY` will be removed once at least one `AIProvider` + `AIModel` row is
required on first-run setup. Operators running the fallback path will see a deprecation
warning logged on every chat request.

---

## Wagtail admin surface

Both models are registered as Wagtail snippets. Operators configure providers and models
from the Wagtail admin without needing Django admin access.

```python
# phoxtail/agent/wagtail_hooks.py

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

class AIProviderViewSet(SnippetViewSet):
    model = AIProvider
    list_display = ["display_name", "provider_type", "is_active"]
    # api_key_env_var intentionally absent from list_display —
    # the column would expose which env var holds the key to anyone with snippet list access.

class AIModelViewSet(SnippetViewSet):
    model = AIModel
    list_display = ["display_name", "provider", "identifier", "is_active", "sort_order"]

register_snippet(AIProviderViewSet)
register_snippet(AIModelViewSet)
```

Access to these snippets is controlled by Wagtail's standard snippet permissions
(`add_aiprovider`, `change_aiprovider`, etc.), which are assigned via the Groups editor.
Restrict them to superusers or a dedicated "AI Admin" group.

---

## Self-hosted model example

A complete provider + model setup for a local Ollama instance running Llama 3.2:

**AIProvider row:**
```
identifier:      local-ollama
display_name:    Local Ollama
provider_type:   openai_compatible
base_url:        http://localhost:11434/v1
api_key_env_var: (blank)
is_active:       true
```

**AIModel row:**
```
provider:    local-ollama
identifier:  llama3.2
display_name: Llama 3.2 (local)
required_permission: (blank — available to all chatbot users)
is_active:   true
sort_order:  10
```

No env var needed. No key rotation. The `base_url` is the only required field beyond the
identifiers.

---

## Security trade-offs

**What this approach protects against:**
- API keys never appear in database rows, dumps, or backups.
- A compromised DB does not yield working API credentials.
- Admin users who can edit `AIProvider` records cannot *read* the key — only change which
  env var name the app reads.

**What this approach does not protect against:**
- An attacker with shell access to the server can read env vars directly. But at that point
  you have a server compromise, not a secrets management problem.
- An attacker who can execute arbitrary Python in the app process can call
  `os.environ.get(provider.api_key_env_var)`. Same threat model as any secrets-in-env
  setup.

**Upgrade path to encrypted-in-DB storage:** If a future requirement demands that operators
paste keys directly into the admin (no shell access to set env vars), add
`django-cryptography` and an `api_key_encrypted` field alongside `api_key_env_var`. The
resolver checks `api_key_encrypted` first, then falls back to the env var. The env-var
path remains valid indefinitely.

**Upgrade path to an external secret store:** Replace the `os.environ.get(...)` call with
a resolver that supports `env:VARNAME`, `aws-ssm:/path/to/param`, or `vault:secret/key`
prefixes. The provider record stores the reference string; the resolver handles dispatch.
No schema change required.
