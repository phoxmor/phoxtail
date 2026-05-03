# In-House Chatbot

The Phoxtail design bar includes a built-in AI chatbot that gives authenticated users a conversational interface to the same tools available to Claude Code in the terminal. This is a different path from the [Remote Connector](remote-connector.md), which wires Claude.ai directly to the MCP server over HTTP. Both paths are valid and can coexist; this document covers the in-house path only.

---

## Vision

The chatbot is the crowning jewel of the Phoxtail architecture — the point where the full stack pays off. Until now, managing a Phoxtail project with an AI agent meant opening a terminal, activating an environment, and running Claude Code in the project root. That path stays available and remains the right choice for developers. But it is no longer the primary path.

The primary path is a button in the design bar. A user on any device, in any browser, on any page of their site presses that button, a drawer opens, and they have a conversational interface to the same MCP tools that power Claude Code — without a terminal, without local setup, without an external AI subscription. The interface is owned by the Phoxtail project itself, running against the project's own database, authenticated through the existing Django session.

Three paths coexist, ranked by where investment is going:

1. **In-house chatbot** (this document) — the primary interface; built into the design bar, runs in the browser.
2. **Terminal + Claude Code** — the developer path; unchanged, always available.
3. **Remote connector** ([`remote-connector.md`](remote-connector.md)) — future path; wires Claude.ai's web interface to the MCP server over OAuth 2.1.

The model layer is a commodity detail. "Claude Code is just an interface — we'll still be talking to those brains anyway." Anthropic, Google Gemini, and any OpenAI-compatible endpoint are interchangeable via PydanticAI's model abstraction. The real frontier is not which API you call: it is owning the interface, the conversation history, and ultimately the inference layer itself. The long arc of this architecture ends at self-hosted GPU inference — rented or owned hardware running open-source models such as Gemma 4 or Qwen — where the model abstraction becomes a config entry pointing at your own server. API providers are the on-ramp; that is the destination.

---

## Why in-house instead of remote connector?

The remote connector delegates the AI layer entirely to Claude.ai: your MCP tools run server-side, but the model, conversation history, and UX live in Claude's app. That's a strong path for power users who are already in Claude.ai, but it requires OAuth 2.1, Dynamic Client Registration, a public HTTPS endpoint, and an external subscription.

The in-house chatbot embeds the full loop — UI, model call, tool execution, conversation history — inside the Phoxtail project itself. Benefits:

- Works in local dev with no external dependencies (Ollama)
- No OAuth; auth is `request.user` from the Django session (access model is a deployment decision, not an architecture one)
- Model is swappable: Google Gemini, Anthropic, or any PydanticAI-supported endpoint (Ollama, OpenAI-compatible)
- Conversation history is persisted in the project's own database
- The path to self-hosted GPU inference (Gemma, Qwen, etc.) is a config change, not an architecture change

---

## How MCP tools are reused

The MCP server (FastMCP, `phoxtail/mcp/`) exposes tools over the stdio/HTTP wire protocol for external clients like Claude Code. The chatbot does **not** use the wire protocol. Instead it calls the same Python functions directly, in-process.

Each MCP tool is a plain Python function decorated with `@mcp_server.tool(...)` that calls `phoxtail/mcp/_http.py` to reach the Django API over HTTP. The chatbot backend wraps those functions as PydanticAI `Tool` objects in `tools.py` and passes them to the agent — no wire protocol, no serialization overhead.

**Tool call path: direct loopback for MVP; service layer is the target architecture.**

For the MVP, each wrapped tool internally calls `_http.py`, which issues an HTTP request to `localhost` — a loopback to the Django API running in the same process. The chain is:

```
chatbot view  →  PydanticAI Agent  →  Tool.fn()  →  _http.py  →  HTTP  →  localhost/api/…  →  Django view  →  ORM
```

This works and requires zero refactoring. It is a bridge, not the destination.

**The target architecture** separates the logic currently fused inside each tool function into a proper service layer:

```
# Today — logic and HTTP transport are fused inside the tool
def phoxtail_pages_list_pages(...):
    return _http.request("GET", "/api/content/v1/pages/", ...)

# Target — logic extracted; tool registration is a thin wrapper
def list_pages(...):                  # plain service fn; calls ORM directly
    return Page.objects.filter(...)

@mcp_server.tool(...)                 # registration wrapper only
def phoxtail_pages_list_pages(...):
    return list_pages(...)
```

In the target state, three consumers share the same service functions: the Django API endpoints, the MCP tools, and the chatbot backend. No loopback, no HTTP overhead, no server calling itself over the network. This is the architecture that scales.

The refactor is mechanical, not complex — it touches every tool function and every API endpoint that currently contains logic. It is deferred until after a working MVP ships so that scope does not expand before anything runs.

---

## Architecture overview

```
Browser (design bar)
  │  SSE / fetch
  ▼
Django view  ──────────────────────────────────────────────────
  │  phoxtail/agent/api/v1/chat.py
  │
  ├─ Conversation model  (phoxtail/agent/models.py)
  │     message_history = JSONField  (PydanticAI ModelMessages)
  │
  ├─ PydanticAI Agent  (phoxtail/agent/llm.py)
  │     GoogleModel("gemini-2.5-flash") by default
  │     model swappable via PHOXTAIL_CHATBOT_MODEL env var
  │
  └─ Tool wrappers  (phoxtail/agent/tools.py)
        MCP tools wrapped as PydanticAI Tool objects
        calls phoxtail/mcp/…/tool_fn() directly (loopback to Django API)
```

The agent loop runs server-side inside the view, driven by PydanticAI's `Agent.run()`. On each turn:

1. Load the `Conversation` record and deserialize `message_history`.
2. Call `agent.run(user_text, message_history=history, event_stream_handler=handler)`.
3. PydanticAI handles the full agentic loop: tool calls, tool results, multi-turn reasoning.
4. The `event_stream_handler` emits `token`, `tool_start`, `tool_end`, and `blocks_changed` events via an `asyncio.Queue`.
5. A sync generator bridges the async queue to `StreamingHttpResponse` (SSE).
6. On completion, persist the updated `message_history` back to the `Conversation` record.

---

## New Django app: `phoxtail/agent/`

| File | Purpose |
|---|---|
| `models.py` | `Conversation` with `message_history = JSONField` |
| `llm.py` | PydanticAI `Agent` factory; model selected via env var |
| `tools.py` | Wraps FastMCP tools as PydanticAI `Tool` objects |
| `api/v1/chat.py` | `POST /api/agent/v1/chat/stream/` SSE endpoint; `GET /api/agent/v1/conversations/{uuid}/` |

### Models

```python
class Conversation(UUIDMixin, TimestampMixin):
    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    message_history = JSONField(default=list)
    # message_history stores PydanticAI ModelMessages serialized via
    # ModelMessagesTypeAdapter.dump_python(..., mode="json")
```

Conversation history is stored as a single JSON blob per conversation, not as relational `Message`/`ToolCall` rows. PydanticAI's `ModelMessagesTypeAdapter` handles serialization and deserialization. This keeps the schema simple and avoids ORM reconstruction of structured tool-call turns.

---

## Provider abstraction

The chatbot uses **PydanticAI** as the agent framework. `llm.py` constructs a PydanticAI `Agent` backed by `GoogleModel` (Gemini). PydanticAI handles:

- The agentic loop (tool calls, tool results, multi-turn)
- Message history management
- Structured streaming via `event_stream_handler`
- Tool schema extraction and validation

There is no hand-rolled provider adapter. Switching providers is a one-line change to `llm.py`'s model constructor, or a different PydanticAI model class.

**Default: Google Gemini 2.5 Flash** via PydanticAI's `GoogleModel`. Reasons:

- Free tier covers all prototype traffic (1,500 req/day via Google AI Studio).
- 1M-token context window on the free tier — the full conversation history plus large page content fits without truncation.
- Reliable tool-calling support, which matters more than raw token cost for an agentic loop.
- Flash (not Flash-Lite) is the right model here. Flash-Lite saves money on simple text tasks; it is less reliable on multi-step tool use. The cost difference is negligible at prototype scale.

**DeepSeek is excluded.** DeepSeek models process data through Chinese infrastructure. A CMS chatbot reads and writes client content (page text, block variants, media metadata). Data sovereignty is a real concern for that payload, regardless of price.

**Anthropic Haiku 4.5** is the recommended alternative if Gemini tool-calling proves unreliable in practice. PydanticAI has first-class Anthropic support; switching is a one-line model change.

Model is selected by environment variable — no provider switch needed, PydanticAI infers the provider from the model class:

```env
# Google Gemini (default)
GEMINI_API_KEY=…
PHOXTAIL_CHATBOT_MODEL=gemini-2.5-flash

# To use Anthropic instead, change the model class in llm.py and set:
ANTHROPIC_API_KEY=sk-ant-…
PHOXTAIL_CHATBOT_MODEL=claude-haiku-4-5-20251001
```

---

## Streaming

The browser sends one `fetch` POST to `POST /api/agent/v1/chat/stream/`. The response is a `text/event-stream` (SSE) that emits:

- `event: token` — each text token as the model streams (true token-level streaming)
- `event: tool_start` — tool name when a tool call begins
- `event: tool_end` — tool name when the tool call completes
- `event: blocks_changed` — `{page_id, uuids, kind}` after any per-block write tool; triggers HTMX refresh
- `event: done` — end of turn; carries `conversation_uuid` for multi-turn continuity
- `event: error` — emitted on unhandled exceptions; browser displays a generic error message

HTMX handles the initial form submit. The SSE connection and message-list DOM updates are handled with vanilla `fetch` + `ReadableStream` reader — the HTMX SSE extension is too rigid for tool-call interleaving.

**Implementation note — background event loop.** PydanticAI's `agent.run()` is async. Django views are sync. A persistent daemon thread runs a long-lived `asyncio` event loop; `asyncio.run_coroutine_threadsafe` submits the agent coroutine to it. A `queue.Queue` bridges the async output to the sync generator that feeds `StreamingHttpResponse`. The loop is kept alive across requests because the cached `httpx` client inside PydanticAI/GoogleModel is bound to the loop that created it — recreating the loop per request would raise "Event loop is closed".

---

## Auth

No token exchange, no OAuth. The chatbot endpoint uses `django_auth` (Ninja's session auth), which reads the Django session cookie the browser already has. `request.auth` resolves to the logged-in user; the view gates on `is_superuser`.

Note: the Phoxtail API defaults to `PhoxtailTokenAuth` (Bearer token). The `phoxtail.agent` router overrides this with `django_auth` specifically so that browser fetch calls work without a separate token. Browser POSTs from the same origin carry the session cookie automatically.

When the tool executor calls MCP tool functions, it uses the shared `PHOXTAIL_API_TOKEN` env var via `resolve_token()` in `_http.py`. All chatbot users therefore operate as the token owner (typically superuser). Per-user token threading is the next step after the current MVP; service-layer extraction (tools call ORM directly) is the target.

---

## Tool schema extraction

FastMCP's tool registry is at `mcp_server._tool_manager._tools` — a plain `dict[str, Tool]`. `tools.py` iterates this dict and wraps each entry as a PydanticAI `Tool` object:

```python
def _make_tool(mcp_tool) -> Tool:
    async def fn(**kwargs):
        return await mcp_tool.run(kwargs, context=None)

    async def prepare(ctx, tool_def):
        tool_def.parameters_json_schema = mcp_tool.parameters
        return tool_def

    return Tool(fn, name=mcp_tool.name, description=mcp_tool.description, prepare=prepare)
```

PydanticAI handles schema incompatibility issues (e.g. Gemini-incompatible JSON Schema keys) internally — no manual `_strip_unsupported()` function needed.

---

## Local development with Ollama

PydanticAI supports OpenAI-compatible endpoints. To use Ollama locally, change the model in `llm.py` to use `OpenAIModel` pointed at the Ollama base URL:

```python
from pydantic_ai.models.openai import OpenAIModel
model = OpenAIModel(model_name, base_url="http://localhost:11434/v1", api_key="ollama")
```

Tool calling support varies by model. `qwen2.5:14b` is a reliable default for local dev. Gemma 3 variants have inconsistent tool-use support depending on the version — verify before using for agentic workflows.

---

## Self-hosted GPU inference (future)

The same OpenAI-compatible path works for vLLM and any other inference server. The only change is the endpoint URL and model name in `llm.py`. No other code changes needed.

Target models for self-hosted: Gemma 4, Qwen 3, Mistral family. Hosting on the project's own GPU infrastructure is a deployment decision outside this document.

---

## Implementation plan

1. ✅ **`phoxtail/agent/` scaffold** — app, `Conversation` model with `message_history = JSONField`, migrations, registered in `settings.py`
2. ✅ **Tool registry** — FastMCP tools wrapped as PydanticAI `Tool` objects (`tools.py`)
3. ✅ **Provider layer** — `llm.py` with PydanticAI `Agent` + `GoogleModel`; model selected via `PHOXTAIL_CHATBOT_MODEL` env var
4. ✅ **Agent loop** — `POST /api/agent/v1/chat/stream/` Ninja endpoint; PydanticAI `agent.run()` with `event_stream_handler`; superuser gate via `django_auth`
5. ✅ **SSE streaming** — persistent background asyncio loop; `asyncio.run_coroutine_threadsafe` + `queue.Queue` bridge; `StreamingHttpResponse(text/event-stream)`; true token-level streaming; `tool_start`, `tool_end`, `blocks_changed`, `done`, `error` events
6. ✅ **Design bar integration** — form submit POSTs JSON to `/api/agent/v1/chat/stream/` with CSRF token from cookie; `ReadableStream` reader parses SSE frames; tool call indicators appear/fade for each tool turn; assistant text appended on `token`; conversation UUID tracked for multi-turn continuity; `blocks_changed` event triggers per-block HTMX refresh
7. **Auth hardening** — per-user token threading into `_http.py`; rate limiting

---

## Current state (all MVP steps complete)

The full stack is implemented and verified working end-to-end. Browser → design bar → SSE stream → PydanticAI agent → MCP tool loopback → Django API → ORM → HTMX per-block refresh.

### What was built

**`phoxtail/agent/`** — new Django app registered in `phoxtail/project_template/src/settings/base.py`:

- `models.py` — `Conversation(UUIDMixin, TimestampMixin)` with `user` FK and `message_history = JSONField(default=list)`. Message history is stored as a single JSON blob (PydanticAI `ModelMessages` format), not as relational rows.
- `apps.py` — `PhoxtailAgentConfig` with `api_version_router = "phoxtail.agent.api.v1.router"` (auto-mounts at `/api/agent/v1/`)
- `tools.py` — wraps each FastMCP tool from `mcp_server._tool_manager._tools` as a PydanticAI `Tool` object; async `fn` calls `mcp_tool.run()`; `prepare` injects the FastMCP parameter schema into the tool definition
- `llm.py` — `get_agent()` factory; returns a singleton PydanticAI `Agent(model=GoogleModel(...), tools=get_tools())`; model name read from `PHOXTAIL_CHATBOT_MODEL` env var (default: `gemini-2.5-flash`)
- `api/v1/chat.py` — `POST /api/agent/v1/chat/stream/` SSE endpoint; persistent background event loop; `_run_turn()` async coroutine handles PydanticAI event stream; `GET /api/agent/v1/conversations/{uuid}/` returns conversation history for browser rehydration

**`phoxtail/cli/templates/requirements/requirements.in`** — added `pydantic-ai[google]` and other runtime deps. Any new phoxtail runtime dep must be added here too, since phoxtail is bind-mounted (not installed as a package) in hatched project Docker containers.

### Auth: current state and path forward

**Current (MVP):** The chat endpoint uses `django_auth` (session cookie), gated to `is_superuser`. The MCP tool loopback calls (`_http.py`) read the shared `PHOXTAIL_API_TOKEN` env var via `resolve_token()`. This means all chatbot sessions operate as that token's owner regardless of the calling user.

**Auth alternatives:**

| Option | Description | Effort |
|---|---|---|
| A (current) | Shared `PHOXTAIL_API_TOKEN` in `.env` | Done; requires superuser gate on view |
| B (next step) | Per-user token minted at turn start, threaded through `_http.py`'s `auth_token` param | Medium |
| C (target) | Service-layer extraction: tools call Django ORM directly, no HTTP loopback, `request.user` is the auth context | Large refactor; documented as target architecture |

---

## Decisions log

| # | Question | Decision |
|---|---|---|
| 1 | Tool call path | Direct loopback for MVP (MCP tools → `_http.py` → Django API); service layer extraction is the target architecture |
| 2 | Agent framework | PydanticAI — handles the agentic loop, tool schema extraction, streaming, and message history management. No hand-rolled provider adapters needed. |
| 3 | Streaming granularity | True token-level text streaming; single `tool_start`/`tool_end` events per tool call; `blocks_changed` event after per-block write tools |
| 4 | FastMCP schema API | `_tool_manager._tools` dict; each tool wrapped as PydanticAI `Tool` via `_make_tool()`; `prepare` callback injects FastMCP's parameter schema |
| 5 | Chat endpoint shape | Single `POST /api/agent/v1/chat/stream/` with nullable `conversation_uuid` in body. Creates a new conversation when omitted; continues existing one when provided. Target shape (`POST /conversations/` + `POST /conversations/{uuid}/messages/`) is deferred post-MVP. |
| 6 | Gemini schema compatibility | PydanticAI's `GoogleModel` handles schema normalization internally. No `_strip_unsupported()` function needed. |
| 7 | Tool result message format | PydanticAI handles tool result formatting for each provider internally. No manual role mapping or `FunctionResponse` construction needed. |
| 8 | Auth in loopback calls | Chat endpoint uses `django_auth` (session), gated to `is_superuser`. MCP loopback calls use shared `PHOXTAIL_API_TOKEN` env var. Per-user token threading is the next step; service layer is the destination. |
| 9 | Background event loop | A single persistent daemon-thread event loop is created once and reused across all requests. PydanticAI/GoogleModel's `httpx` client is bound to the loop that created it — recreating per request raises "Event loop is closed". |
