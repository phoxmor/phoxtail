# Inference Architecture

The Phoxtail agent supports multiple inference providers and models — including
self-hosted endpoints — without code changes between deployments. This document
describes the data model, the naming rationale, the admin surface, and the
forward path toward specialized domain agents and self-trained models.

---

## Three layers

Inference splits cleanly into three conceptual layers. Two are needed now; the
third is documented as a forward path and should not be built before it pulls
its weight.

| Layer | Question it answers | Built now? |
|-------|---------------------|------------|
| `InferenceProvider` | *Where* does inference run? (connection target) | Yes |
| `ModelArtifact`     | *What* model runs? (the model itself)         | Yes |
| `InferenceProfile`  | *Who* is the agent? (persona + tool scope)    | Future |

Each layer is owned by exactly one concern. `Provider` owns the connection.
`ModelArtifact` owns the model identity and access gating. `InferenceProfile`,
when it lands, will own the agent persona — system prompt, MCP tool scope,
sampling parameters, and the domain role (Content Creator, Designer,
Secretary, …).

---

## Why a database-driven design

The simplest possible setup is two env vars: `GEMINI_API_KEY` and
`PHOXTAIL_CHATBOT_MODEL`. That works for a single cloud provider with a static
config. It breaks down in three real scenarios:

**Per-model permission gating.** Basic users may access a fast, cheap model
while power users access a larger one. There is no way to express that with env
vars — it requires a model record with a `permission` field that the chat
endpoint checks against `request.user`.

**Self-hosted endpoints.** A local Ollama instance, a vLLM deployment, or any
OpenAI-compatible server has a different shape than a cloud API: it needs a
`base_url` (e.g. `http://localhost:11434/v1`), may need no API key at all, and
uses the OpenAI wire protocol regardless of what model is actually running.
That cannot be collapsed into `PROVIDER=google` + `MODEL=llama3`.

**Multi-agent specialization (forward).** Phoxtail is moving toward
domain-specialized agents — a Content Creator scoped to `phoxtail.mcp.content`,
a Designer scoped to `phoxtail.mcp.studio`, a Secretary scoped to the booking
domain. Each persona pairs a model with a system prompt and a curated tool
scope. That requires a configurable record per persona (the future
`InferenceProfile`), not a hard-coded agent.

---

## Naming

The names below were chosen deliberately. The reasoning is recorded so the same
debate does not get re-run later.

### `InferenceProvider`, not `AIProvider` or `LLMProvider`

*Inference* is the established ML term for running a trained model to produce
outputs (as opposed to training). It predates the current AI hype by decades
(statistics, logic, ML), and Hugging Face brands their service literally as
"Inference Providers" — the same concept used here.

- *AI* — marketing-flavored, already diluted.
- *LLM* — describes architecture and is increasingly inaccurate as models
  become multimodal.
- *Inference* — describes the function and remains accurate regardless of the
  underlying model architecture.

### `ModelArtifact`, not `ModelDeployment` / `HostedModel` / `InferenceModel`

In ML/MLOps, an **artifact** is the persisted, frozen output of training — a
file (or set of files) of weights and config that can be loaded and run.
Artifact-ness is intrinsic to the *thing*, not to *who produced it*. Hugging
Face, MLflow, and SageMaker all call third-party models artifacts in their
registries.

`gemini-2.5-flash` is an artifact (Google trained, froze, versioned, exposed
it). A future Phoxtail fine-tune is also an artifact. The same Django model
holds both — today as a string identifier referencing a third-party artifact,
tomorrow growing fields like `parent_model`, `weights_path`, `architecture`
when Phoxtail ships its own.

Rejected alternatives:

- *ModelDeployment* — emphasizes *where it is served*, but that information
  belongs on `InferenceProvider` (`base_url`). Mixing deployment semantics
  into the row that holds permissions and display name muddles the layer.
- *HostedModel* — accurate today, breaks once Phoxtail itself becomes the host.
- *InferenceModel* — slightly redundant ("a model used for inference"), and
  collides mentally with Django's `models.Model`.
- Bare `Model` — `class Model(models.Model)` is grep-hostile and forces
  aliased imports at every call site.

### `InferenceProfile` (future)

A profile is a named, reusable configuration record. AWS Bedrock uses
"Inference Profiles" as a first-class concept for routing requests to specific
models with named configurations — the same problem space, the same word.

When this layer arrives, an `InferenceProfile` row is the agent persona:
"Content Creator" = a `ModelArtifact` + a system prompt + a curated MCP tool
scope + sampling parameters. The chatbot's selectable agents become
`InferenceProfile` rows, not hard-coded `Agent` instances.

---

## Data models (today)

```python
# phoxtail/agent/models.py

from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.models import Orderable
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin


class InferenceProvider(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, models.Model
):
    """A connection target: a cloud API, a local server, or any
    OpenAI-compatible endpoint."""

    identifier      = models.SlugField(unique=True)
    display_name    = models.CharField(max_length=100)
    model_prefix    = models.CharField(max_length=64, blank=True)
    # ^ pydantic-ai model-string prefix, e.g. "google-gla", "anthropic",
    #   "openai". Free-form — adding a new cloud provider is typing a prefix
    #   into the admin, no code change required.
    base_url        = models.URLField(blank=True)
    # ^ set for self-hosted / OpenAI-compatible endpoints. When present,
    #   dispatch always uses OpenAIChatModel(base_url=...).
    api_key_env_var = models.CharField(max_length=200, blank=True)
    # ^ the *name* of the env var, not the key itself (e.g. "GEMINI_API_KEY").
    #   Blank for unauthenticated local providers.
    is_active       = models.BooleanField(default=True)

    search_fields = [
        index.SearchField("display_name"),
        index.AutocompleteField("display_name"),
        index.FilterField("is_active"),
    ]

    class Meta:
        ordering = ["display_name"]


class ModelArtifact(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, Orderable
):
    """A registered, addressable model — third-party today, possibly
    Phoxtail-trained tomorrow."""

    provider     = models.ForeignKey(
        InferenceProvider, on_delete=models.CASCADE, related_name="artifacts"
    )
    identifier   = models.CharField(max_length=200)
    # ^ the model name the API accepts, e.g. "gemini-2.5-flash", "llama3.2".
    display_name = models.CharField(max_length=100)
    permission   = models.ForeignKey(
        "auth.Permission", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    # ^ if set, the user must hold this permission to select this artifact.
    #   null = available to all users who can access the chatbot.
    is_active    = models.BooleanField(default=True)

    search_fields = [
        index.SearchField("display_name"),
        index.SearchField("identifier"),
        index.FilterField("is_active"),
        index.FilterField("provider"),
    ]

    class Meta(Orderable.Meta):
        unique_together = [["provider", "identifier"]]


@register_setting(icon="cognition-2")
class AgentSiteSetting(BaseSiteSetting):
    """Per-site agent configuration. Stored in the Wagtail site settings."""

    default_artifact = models.ForeignKey(
        ModelArtifact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # ^ the artifact used when a chat request omits artifact_id.
    #   If null, the endpoint returns 400 and the UI prompts the user to
    #   pick a model explicitly.

    panels = [FieldPanel("default_artifact")]

    class Meta:
        verbose_name = "Agent"
```

`Orderable` provides the `sort_order` field and the correct Meta ordering — no
need to redeclare it. `index.Indexed` lets the artifact participate in Wagtail
search and snippet filtering, consistent with `Conversation` and other project
models.

### The env-var-name pattern

The API key never enters the database. The provider record stores the *name*
of the environment variable the operator has set on the server (e.g.
`"GEMINI_API_KEY"`). At runtime the agent factory resolves it:

```python
api_key = os.environ.get(provider.api_key_env_var) if provider.api_key_env_var else None
```

This keeps secrets in the environment — out of DB dumps, backups, and admin
audit logs — while letting the admin configure which env var each provider
uses without a deploy.

For self-hosted providers with no authentication, leave `api_key_env_var`
blank. The agent factory sends `"EMPTY"` as a dummy value so that
OpenAI-compatible servers that require a non-empty `Authorization` header (e.g.
vLLM with default config) do not reject the request.

**Cache invalidation note.** The agent is cached per `(provider, artifact)` pair
using their `updated_at` timestamps as the cache key. If you add an env var to
the server *after* the first request, touch the provider record in the admin
(e.g. save without changes) to bust the cache and force the agent to re-read
the new value.

---

## Per-site default model

The default model is stored in `AgentSiteSetting.default_artifact` — a
per-site Wagtail setting. This allows multi-site Phoxtail deployments to
configure a different default model per site.

When a chat request omits `artifact_id`, the endpoint resolves the requesting
site's setting via `AgentSiteSetting.for_request(request)`. If no default is
configured for that site, the endpoint returns 400 and the UI prompts the user
to pick a model explicitly.

Bootstrap creates the setting automatically: migration `0008_agentsettings`
reads the `is_default=True` artifact (set by migration `0007`) and writes it
to `AgentSiteSetting` for the default site, then removes `is_default` from
`ModelArtifact`. After that, the only authoritative source of the default is
`AgentSiteSetting`.

---

## Per-turn model switching

The model is a property of the *request*, not the *conversation*. Matches the
UX of Claude.ai, Gemini, and ChatGPT — the user may switch on any turn.

```python
class StreamRequest(Schema):
    message: str
    conversation_uuid: str | None = None
    artifact_id: int | None = None
    # ^ pk of the ModelArtifact to use for this turn.
    #   None = use AgentSiteSetting.default_artifact for the requesting site;
    #   400 if none is configured.
```

`Conversation` stores `last_artifact_used` as a UI hint only — so the
frontend can pre-select the same artifact on the next turn as a convenience.
It does not constrain which artifact the next request uses.

```python
class Conversation(models.Model):
    ...
    last_artifact_used = models.ForeignKey(
        "ModelArtifact", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
```

---

## Permission gating

In the chat endpoint, after resolving the requested artifact, check
`permission`:

```python
artifact = (
    ModelArtifact.objects.select_related("provider", "permission__content_type")
    .filter(pk=payload.artifact_id, is_active=True, provider__is_active=True)
    .first()
)
if artifact is None:
    raise HttpError(404, "Model not found.")

if artifact.permission:
    ct = artifact.permission.content_type
    perm = f"{ct.app_label}.{artifact.permission.codename}"
    if not user.has_perm(perm):
        raise HttpError(403, "You do not have access to this model.")
```

Both `artifact.is_active` and `artifact.provider.is_active` are checked.
Deactivating a provider hides all its artifacts from the picker and rejects
requests that name them directly.

This composes naturally with the coarse-grained `access_chatbot` gate that
runs before it: a user must pass the chatbot permission first, then the
per-artifact permission.

---

## Agent factory

The only dispatch decision is: does the provider have a `base_url`? If yes,
use `OpenAIChatModel` with that URL. If no, pass a pydantic-ai model string
built from `model_prefix` + `identifier`.

```python
# phoxtail/agent/llm.py
# Verify constructor signatures against the installed pydantic-ai version —
# the API surface evolves quickly.

import os
from functools import lru_cache
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from .tools import get_tools


@lru_cache(maxsize=16)
def _build_agent(
    model_prefix: str,
    identifier: str,
    base_url: str | None,
    api_key_env_var: str | None,
    cache_key: str,
) -> Agent:
    api_key = os.environ.get(api_key_env_var) if api_key_env_var else None

    if base_url:
        # Always send api_key so OpenAI-compat servers that require a
        # non-empty Authorization header (e.g. vLLM) don't reject the request.
        model = OpenAIChatModel(identifier, base_url=base_url, api_key=api_key or "EMPTY")
    else:
        # pydantic-ai accepts "<prefix>:<identifier>" model strings directly.
        model = f"{model_prefix}:{identifier}" if model_prefix else identifier

    return Agent(model=model, tools=get_tools())


def get_agent(artifact: "ModelArtifact") -> Agent:
    provider = artifact.provider
    return _build_agent(
        model_prefix=provider.model_prefix or "",
        identifier=artifact.identifier,
        base_url=provider.base_url or None,
        api_key_env_var=provider.api_key_env_var or None,
        cache_key=f"{provider.updated_at.timestamp()}|{artifact.updated_at.timestamp()}",
    )
```

### Cache invalidation

`cache_key` carries `updated_at` from both the provider and the artifact.
Editing either record in the Wagtail admin bumps `updated_at`, which produces
a new cache key and builds a fresh `Agent`. Old entries age out of the LRU
naturally. This avoids the trap where editing `base_url` in the admin has no
effect until process restart.

---

## Bootstrap

A one-shot data migration (split across three steps) creates a default
`InferenceProvider` and `AgentSiteSetting` from environment variables, so
existing deployments keep working without admin intervention:

1. **`0005_inferenceprovider_modelartifact`** — creates the tables.
2. **`0006_seed_default_inference`** — inserts a `google-gemini` provider and a
   `gemini-2.5-flash` artifact if no providers exist yet.
3. **`0007_modelartifact_is_default`** — adds a temporary `is_default` field and
   marks the seeded artifact as default.
4. **`0008_agentsettings`** — creates `AgentSiteSetting`, copies the
   `is_default=True` artifact to `AgentSiteSetting.default_artifact` for the
   default site, then removes `is_default` from `ModelArtifact`.
5. **`0009_rename_agentsettings_agentsitesetting`** — renames the model to
   `AgentSiteSetting`.

After migrations, every chat request goes through the same
`get_agent(artifact)` codepath. The env var `GEMINI_API_KEY` continues to work
because the seeded provider references it by name; operators can edit or
replace the records freely from the admin.

---

## Wagtail admin surface

Both models register as Wagtail snippets. Operators configure providers and
artifacts from the Wagtail admin without needing Django admin access.

```python
# phoxtail/agent/wagtail_hooks.py

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet


class InferenceProviderViewSet(SnippetViewSet):
    model = InferenceProvider
    list_display = [
        "display_name", "model_prefix", "base_url",
        "api_key_env_var", "is_active",
    ]
    # api_key_env_var is shown deliberately: env var names are not secrets
    # (the values are), and operators need to see at a glance whether a
    # provider is misconfigured.


class ModelArtifactViewSet(SnippetViewSet):
    model = ModelArtifact
    list_display = [
        "display_name", "provider", "identifier",
        "permission", "is_active", "sort_order",
    ]


register_snippet(InferenceProviderViewSet)
register_snippet(ModelArtifactViewSet)
```

`AgentSiteSetting` appears in the Wagtail **Settings** menu (registered via
`@register_setting`). Access is controlled by Wagtail's standard snippet and
settings permissions, assignable via the Groups editor. Restrict to superusers
or a dedicated "AI Admin" group.

---

## Self-hosted example

A local Ollama instance running Llama 3.2:

**InferenceProvider:**
```
identifier:      local-ollama
display_name:    Local Ollama
model_prefix:    (blank)
base_url:        http://localhost:11434/v1
api_key_env_var: (blank)
is_active:       true
```

**ModelArtifact:**
```
provider:     local-ollama
identifier:   llama3.2
display_name: Llama 3.2 (local)
permission:   (blank — available to all chatbot users)
is_active:    true
sort_order:   10
```

No env var needed. No key rotation. The presence of `base_url` triggers the
`OpenAIChatModel(base_url=..., api_key="EMPTY")` codepath automatically.

**Set as default** by opening Site Settings → Agent in the Wagtail admin and
selecting this artifact as `default_artifact`.

---

## Forward path

The two models above are sufficient for today's chatbot. The sections below
document the natural growth direction so future work does not require a schema
rewrite or a naming change.

### Multi-agent specialization: `InferenceProfile`

The Phoxtail codebase already organizes itself around domain specialists:

- `phoxtail.mcp.content` — content tools (pages, body, media, blocks, links)
- `phoxtail.mcp.studio` — design system tools (variants, blocks, collections)
- `phoxtail.booking` — booking-domain tools (reservations, services, …)

The natural next step is a configurable record per persona — one
`InferenceProfile` per specialist agent:

```python
class InferenceProfile(
    UUIDMixin, TimestampMixin, AdminURLMixin, index.Indexed, Orderable
):
    """A specialized agent persona: model + system prompt + tool scope."""
    identifier    = models.SlugField(unique=True)
    display_name  = models.CharField(max_length=100)
    artifact      = models.ForeignKey(ModelArtifact, on_delete=models.PROTECT)
    system_prompt = models.TextField()
    mcp_modules   = models.JSONField(default=list)
    # ^ list of phoxtail.mcp_modules entry-point names this persona can use.
    temperature   = models.FloatField(null=True, blank=True)
    max_tokens    = models.IntegerField(null=True, blank=True)
    permission    = models.ForeignKey(
        "auth.Permission", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    is_active     = models.BooleanField(default=True)
```

Rows like *Content Creator*, *Designer*, *Secretary* become first-class
admin-editable records. The chat request switches from "pick an artifact" to
"pick a profile"; the agent factory composes the artifact's model with the
profile's system prompt and MCP tool scope.

This layer is **not built today** because the current chatbot has one system
prompt baked in and no per-persona tool scoping. Build it when the second
persona ships — that is when the layer earns its keep.

### Self-trained models

`ModelArtifact` is named so it accommodates Phoxtail-owned models without a
rename. When that work begins, the same table grows:

```python
parent_model    = models.ForeignKey("self", null=True, blank=True,
                                    on_delete=models.SET_NULL)
# ^ fine-tune lineage. Null for base models; set for fine-tunes.
weights_path    = models.CharField(max_length=500, blank=True)
# ^ S3/GCS URI or local path to the artifact file.
architecture    = models.CharField(max_length=100, blank=True)
# ^ "Llama-3.2", "Transformer", etc.
framework       = models.CharField(max_length=50, blank=True)
# ^ "PyTorch", "GGUF", "ONNX".
hyperparameters = models.JSONField(default=dict, blank=True)
base_metrics    = models.JSONField(default=dict, blank=True)
```

A Phoxtail fine-tune served via a self-hosted vLLM instance becomes:

- An `InferenceProvider` row pointing to the vLLM `base_url`.
- A `ModelArtifact` row with `parent_model` set to the base model row,
  `weights_path` pointing to artifact storage, and the metadata fields above.

No schema rewrite. No rename. The path from third-party consumer to
self-trained provider is one set of `AddField` migrations.

### Phoxtail as a provider

If Phoxtail eventually monetizes fine-tuned artifacts to other Phoxtail
deployments, Phoxtail itself becomes an `InferenceProvider` from the
consumer's perspective — same data model, no special case. The architecture
does not encode any assumption that providers are always external.

---

## Security trade-offs

**What this approach protects against:**

- API keys never appear in DB rows, dumps, or backups.
- A compromised DB does not yield working API credentials.
- Admins who can edit `InferenceProvider` records cannot *read* the key —
  only change which env var name the app reads.

**What it does not protect against:**

- An attacker with shell access to the server can read env vars directly.
  At that point the threat is server compromise, not secrets management.
- An attacker who can execute arbitrary Python in the app process can call
  `os.environ.get(...)` themselves. Same threat model as any secrets-in-env
  setup.

**Upgrade path to encrypted-in-DB storage.** Add `django-cryptography` and
an `api_key_encrypted` field alongside `api_key_env_var`. The resolver checks
`api_key_encrypted` first, then falls back to the env var.

**Upgrade path to an external secret store.** Replace `os.environ.get(...)`
with a resolver that supports `env:VARNAME`, `aws-ssm:/path/to/param`, or
`vault:secret/key` prefixes. The provider record stores the reference string;
the resolver handles dispatch. No schema change required.

---

## Dependency hygiene

`pydantic-ai` (the meta-package) installs `pydantic-ai-slim` with all provider
extras, which includes `[google]`. That extra pins `google-genai>=1.70.0`. The
explicit `google-genai>=1.0.0` entries previously in `requirements.in` and the
`[chatbot]` extra in `pyproject.toml` have been removed as redundant.

If install size becomes a concern, switching from `pydantic-ai` to
`pydantic-ai-slim[google,openai,anthropic]` (or whatever subset is active)
is the right move — but that is a separate decision from the dependency cleanup.
