"""Agent chat endpoint — /api/agent/v1/chat/stream/"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import re
import threading
import time
import uuid
from collections.abc import AsyncIterable
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from ninja import Router, Schema

if TYPE_CHECKING:
    from pydantic_ai import RunContext

from phoxtail.agent.chat_blocks import (
    CHAT_BLOCK_TOOLS,
    pop_pending,
    render_chat_block,
    render_history_tool_call,
    try_parse_partial_json,
)
from phoxtail.agent.llm import get_agent
from phoxtail.agent.markdown import render_chat_markdown
from phoxtail.agent.models import AgentSiteSetting, Conversation, ModelArtifact
from phoxtail.agent.permissions import agent_permission_policy

router = Router()

_SENTINEL = object()
_CONTEXT_STRIP = re.compile(r"^<phoxtail-context>\n[\s\S]*?\n</phoxtail-context>\n\n")

# ── Persistent background event loop ────────────────────────────────────────
# asyncio.run() creates and destroys a loop per call. The cached agent's httpx
# client is bound to the first loop; reuse on a new loop raises "Event loop is
# closed". A single long-lived loop avoids this.

_bg_loop: asyncio.AbstractEventLoop | None = None
_bg_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _bg_loop
    with _bg_loop_lock:
        if _bg_loop is None or _bg_loop.is_closed():
            _bg_loop = asyncio.new_event_loop()
            t = threading.Thread(target=_bg_loop.run_forever, daemon=True)
            t.start()
    return _bg_loop


# ── SSE helpers ──────────────────────────────────────────────────────────────


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Async agent turn (runs inside the background loop) ───────────────────────

# Tool names that trigger a blocks_changed SSE event after the tool call.
# "publish" has no per-block UUIDs — it signals a full-body refresh.
_BLOCK_WRITE_TOOLS = {
    "phoxtail_pages_update_block": "update",
    "phoxtail_pages_add_block": "add",
    "phoxtail_pages_delete_block": "delete",
    "phoxtail_pages_move_block": "move",
    "phoxtail_pages_publish": "publish",
}


async def _run_turn(conversation_pk: int, user_text: str, out: queue.Queue, artifact_pk: int) -> None:
    # pydantic_ai is imported per-call (see llm.py) so processes that never
    # serve a chat turn never pay its ~50MB import cost. First chat call in a
    # process imports it once; afterwards these are sys.modules lookups.
    from pydantic_ai import (
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        PartStartEvent,
        TextPartDelta,
    )
    from pydantic_ai.messages import (
        ModelMessagesTypeAdapter,
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        ToolCallPartDelta,
        UserPromptPart,
    )

    # handler()'s ``ctx: RunContext`` annotation is a string (future
    # annotations); bind the name into module globals so it resolves if
    # pydantic_ai ever introspects the handler via get_type_hints().
    global RunContext
    from pydantic_ai import RunContext

    # Setup (fetching the conversation/artifact, building the agent) happens
    # outside the try/finally below that guarantees `out` gets a sentinel. If
    # it raises here — e.g. a misconfigured provider — the consumer in
    # _stream_turn_sync would otherwise block on out.get() forever, since no
    # sentinel would ever arrive. Catch, surface as an SSE error, and re-raise
    # so it still propagates to the server logs via future.result().
    try:
        conversation = await sync_to_async(Conversation.objects.get)(pk=conversation_pk)
        artifact = await sync_to_async(ModelArtifact.objects.select_related("provider").get)(pk=artifact_pk)
        history = ModelMessagesTypeAdapter.validate_python(conversation.message_history)
        agent = get_agent(artifact)
    except Exception:
        out.put(_sse("error", {"message": "An error occurred. Please try again."}))
        out.put(_SENTINEL)
        raise

    aq: asyncio.Queue[Any] = asyncio.Queue()
    text_sent = False
    # Stash tool-call args keyed by tool_call_id so we can extract page_id on result.
    _pending_args: dict[str, dict[str, Any]] = {}
    # Accumulates streamed text so we can persist a partial response on cancellation.
    _partial_text: list[str] = []
    # Speculative chat-block streaming: render_block tool-call args accumulate
    # here (keyed by part index) and are best-effort rendered as they grow.
    _block_streams: dict[Any, dict[str, Any]] = {}
    # The currently-streaming prose part. Accumulated raw markdown is
    # re-rendered server-side on a throttle and upserted into one bubble via
    # its stream_id; the part is flushed (final, unthrottled render) when the
    # next part starts or the model response ends.
    _open_text: dict[str, Any] | None = None

    async def _emit_text(state: dict[str, Any], final: bool) -> None:
        now = time.monotonic()
        if not final and now - state["last_render"] < 0.15:
            return
        state["last_render"] = now
        text = "".join(state["buf"])
        if not text.strip():
            return
        await aq.put(("message_html", state["stream_id"], render_chat_markdown(text), not final))

    async def _flush_text() -> None:
        nonlocal _open_text
        if _open_text is not None:
            await _emit_text(_open_text, final=True)
            _open_text = None

    async def _render_partial_block(state: dict[str, Any]) -> None:
        """Throttled best-effort render of a partially-streamed render_block call."""
        now = time.monotonic()
        if now - state["last_render"] < 0.15:
            return
        state["last_render"] = now
        parsed = try_parse_partial_json("".join(state["buf"]))
        if not parsed or not parsed.get("identifier") or not isinstance(parsed.get("value"), dict):
            return
        try:
            html = await sync_to_async(render_chat_block)(
                parsed["identifier"],
                parsed["value"],
                state["dom_id"],
                validate=False,
            )
        except Exception:
            return  # incomplete value shapes are expected mid-stream
        await aq.put(("chat_block_partial", state["stream_id"], html))

    async def handler(ctx: RunContext, events: AsyncIterable) -> None:
        nonlocal text_sent, _open_text
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                _pending_args[event.tool_call_id] = event.part.args_as_dict()
                await aq.put(("tool_start", event.part.tool_name))
            elif isinstance(event, FunctionToolResultEvent):
                tool_name = event.part.tool_name
                kind = _BLOCK_WRITE_TOOLS.get(tool_name)
                if kind is not None:
                    args = _pending_args.get(event.tool_call_id, {})
                    page_id = args.get("page_id")
                    if page_id is not None:
                        if kind == "publish":
                            # No per-block UUIDs — full-body refresh.
                            # Only emit if the publish succeeded (no error envelope).
                            try:
                                result_content = str(event.part.content) if hasattr(event.part, "content") else ""
                                if "error" not in json.loads(result_content):
                                    await aq.put(("blocks_changed", int(page_id), [], kind))
                            except (
                                json.JSONDecodeError,
                                AttributeError,
                                TypeError,
                                ValueError,
                            ):
                                pass
                        else:
                            # Extract _changed_blocks from the tool result JSON.
                            # ToolReturnPart.content is the raw return value; our
                            # tools always return a JSON string.
                            try:
                                result_content = str(event.part.content) if hasattr(event.part, "content") else ""
                                changed = json.loads(result_content).get("_changed_blocks")
                                if changed:
                                    await aq.put(("blocks_changed", int(page_id), changed, kind))
                            except (
                                json.JSONDecodeError,
                                AttributeError,
                                TypeError,
                                ValueError,
                            ):
                                pass
                if tool_name in CHAT_BLOCK_TOOLS:
                    # The tool stashed its rendered payload keyed by the
                    # chat_block_id in its result JSON. Pop it and push it to
                    # the browser; on error results there is nothing to pop.
                    try:
                        result_content = str(event.part.content) if hasattr(event.part, "content") else ""
                        chat_block_id = json.loads(result_content).get("chat_block_id")
                    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
                        chat_block_id = None
                    payload = pop_pending(chat_block_id) if chat_block_id else None
                    # Close this call's speculative preview shell: the final
                    # render must reuse its stream_id to replace it in place.
                    # The stream_id can be an index-based fallback when the
                    # provider omitted tool_call_id at part start, so match by
                    # id first, else claim the only open stream.
                    partial_stream_id = None
                    for index, state in list(_block_streams.items()):
                        if state["stream_id"] == event.tool_call_id or len(_block_streams) == 1:
                            partial_stream_id = state["stream_id"]
                            del _block_streams[index]
                            break
                    if payload:
                        kind = payload.pop("kind")
                        await aq.put(("chat_block", kind, payload, partial_stream_id or event.tool_call_id))
                    elif partial_stream_id:
                        # Tool errored — remove the half-rendered preview.
                        await aq.put(("chat_block_gone", partial_stream_id))
                await aq.put(("tool_end", tool_name))
            elif isinstance(event, PartStartEvent) and isinstance(event.part, ToolCallPart):
                await _flush_text()
                # Begin speculative streaming for render_block calls.
                if event.part.tool_name == "render_block":
                    initial = event.part.args if isinstance(event.part.args, str) else ""
                    _block_streams[event.index] = {
                        "buf": [initial],
                        "stream_id": event.part.tool_call_id or f"idx-{event.index}",
                        "dom_id": f"chat-stream-{event.index}",
                        "last_render": 0.0,
                    }
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, ToolCallPartDelta):
                state = _block_streams.get(event.index)
                if state is not None and isinstance(event.delta.args_delta, str):
                    state["buf"].append(event.delta.args_delta)
                    try:
                        await _render_partial_block(state)
                    except Exception:
                        pass  # streaming preview is best-effort, never fatal
            elif isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                await _flush_text()
                _open_text = {
                    "buf": [event.part.content or ""],
                    "stream_id": f"txt-{uuid.uuid4().hex[:12]}",
                    "last_render": 0.0,
                }
                if event.part.content:
                    text_sent = True
                    _partial_text.append(event.part.content)
                    await _emit_text(_open_text, final=False)
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                if event.delta.content_delta and _open_text is not None:
                    text_sent = True
                    _partial_text.append(event.delta.content_delta)
                    _open_text["buf"].append(event.delta.content_delta)
                    await _emit_text(_open_text, final=False)
        # Model response finished streaming — final authoritative render.
        await _flush_text()

    async def produce() -> None:
        nonlocal text_sent
        try:
            result = await agent.run(
                user_text,
                message_history=history,
                event_stream_handler=handler,
            )
            # Fallback: if no text streamed, emit the full output now
            if not text_sent and result.output:
                _partial_text.append(str(result.output))
                html = render_chat_markdown(str(result.output))
                await aq.put(("message_html", f"txt-{uuid.uuid4().hex[:12]}", html, False))

            updated = history + list(result.new_messages())
            conversation.message_history = ModelMessagesTypeAdapter.dump_python(updated, mode="json")
            conversation.last_artifact_used_id = artifact_pk
            await sync_to_async(conversation.save)(
                update_fields=["message_history", "updated_at", "last_artifact_used"]
            )
            if not conversation.title:
                stripped = _CONTEXT_STRIP.sub("", user_text).strip()
                if stripped:
                    conversation.title = stripped[:80]
                    await sync_to_async(conversation.save)(update_fields=["title", "updated_at"])
        finally:
            await aq.put(_SENTINEL)

    async def _save_partial() -> None:
        """Persist the user message and any streamed text accumulated so far."""
        try:
            user_msg = ModelRequest(parts=[UserPromptPart(content=user_text)])
            new_msgs: list = [user_msg]
            partial = "".join(_partial_text)
            if partial:
                new_msgs.append(ModelResponse(parts=[TextPart(content=partial)]))
            updated = history + new_msgs
            conversation.message_history = ModelMessagesTypeAdapter.dump_python(updated, mode="json")
            conversation.last_artifact_used_id = artifact_pk
            await sync_to_async(conversation.save)(
                update_fields=["message_history", "updated_at", "last_artifact_used"]
            )
            if not conversation.title:
                stripped = _CONTEXT_STRIP.sub("", user_text).strip()
                if stripped:
                    conversation.title = stripped[:80]
                    await sync_to_async(conversation.save)(update_fields=["title", "updated_at"])
        except Exception:
            pass

    producer = asyncio.create_task(produce())
    try:
        while True:
            item = await aq.get()
            if item is _SENTINEL:
                break
            kind, *rest = item
            if kind == "message_html":
                stream_id, html, partial = rest
                out.put(_sse("message_html", {"html": html, "stream_id": stream_id, "partial": partial}))
            elif kind == "tool_start":
                out.put(_sse("tool_start", {"name": rest[0]}))
            elif kind == "tool_end":
                out.put(_sse("tool_end", {"name": rest[0]}))
            elif kind == "chat_block_partial":
                stream_id, html = rest
                out.put(_sse("block_html", {"html": html, "stream_id": stream_id, "partial": True}))
            elif kind == "chat_block_gone":
                out.put(_sse("block_gone", {"stream_id": rest[0]}))
            elif kind == "chat_block":
                block_kind, payload, stream_id = rest
                data = dict(payload)
                data["stream_id"] = stream_id
                out.put(_sse(block_kind, data))
            elif kind == "blocks_changed":
                page_id, uuids, change_kind = rest
                out.put(
                    _sse(
                        "blocks_changed",
                        {"page_id": page_id, "uuids": uuids, "kind": change_kind},
                    )
                )
        await producer
        out.put(_sse("done", {"conversation_uuid": str(conversation.uuid)}))
    except asyncio.CancelledError:
        producer.cancel()
        try:
            await producer
        except (asyncio.CancelledError, Exception):
            pass
        await _save_partial()
        raise
    except Exception as exc:
        from pydantic_ai.exceptions import ModelHTTPError

        if isinstance(exc, ModelHTTPError):
            body = exc.body
            msg = body.get("message", str(exc)) if isinstance(body, dict) else str(exc)
        else:
            msg = "An error occurred. Please try again."
        out.put(_sse("error", {"message": msg}))
        raise
    finally:
        out.put(_SENTINEL)


# ── Sync streaming generator (passed to StreamingHttpResponse) ───────────────


def _stream_turn_sync(conversation_pk: int, user_text: str, artifact_pk: int):
    out: queue.Queue[Any] = queue.Queue()
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(_run_turn(conversation_pk, user_text, out, artifact_pk), loop)

    try:
        while True:
            item = out.get()
            if item is _SENTINEL:
                break
            yield item
    except GeneratorExit:
        future.cancel()
        raise

    future.result()  # re-raise any exception from the async side


# ── Schema ───────────────────────────────────────────────────────────────────


class StreamRequest(Schema):
    message: str
    conversation_uuid: str | None = None
    artifact_id: int | None = None
    # ^ pk of the ModelArtifact to use for this turn.
    #   None = use AgentSiteSetting.default_artifact; 400 if none configured.


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/conversations/{uuid}/", tags=["agent/v1"])
def get_conversation(request, uuid: str):
    from ninja.errors import HttpError
    from pydantic_ai.messages import (
        ModelMessagesTypeAdapter,
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        UserPromptPart,
    )

    user = request.auth
    if not user or not agent_permission_policy.user_has_permission(user, "access_chatbot"):
        raise HttpError(403, "Access denied.")
    try:
        conversation = Conversation.objects.select_related("last_artifact_used").get(uuid=uuid, user=user)
    except Conversation.DoesNotExist:
        raise HttpError(404, "Conversation not found.")

    history = ModelMessagesTypeAdapter.validate_python(conversation.message_history)
    messages = []
    for msg in history:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    messages.append({"role": "user", "content": part.content})
        elif isinstance(msg, ModelResponse):
            # Walk parts in order so chat blocks interleave with prose the
            # same way they streamed. Blocks re-render deterministically from
            # the tool-call args stored in the history — the same way page
            # bodies re-render from stored JSON.
            text_buf: list[str] = []

            def _flush(buf=None):
                buf = text_buf if buf is None else buf
                joined = " ".join(t for t in buf if t).strip()
                if joined:
                    # Same renderer as the live stream, so replayed prose is
                    # bit-identical to what streamed.
                    messages.append({"role": "assistant", "type": "message_html", "html": render_chat_markdown(joined)})
                buf.clear()

            for part in msg.parts:
                if isinstance(part, TextPart):
                    if part.content:
                        text_buf.append(part.content)
                elif isinstance(part, ToolCallPart):
                    _flush()
                    # Every tool call joins the replayed activity trail, so a
                    # reloaded conversation shows the same work the live
                    # stream showed (the pane groups consecutive ones).
                    messages.append({"role": "tool", "name": part.tool_name})
                    if part.tool_name in CHAT_BLOCK_TOOLS:
                        try:
                            item = render_history_tool_call(part.tool_name, part.args_as_dict())
                        except Exception:
                            item = None
                        if item:
                            messages.append(item)
            _flush()

    last_artifact = None
    if conversation.last_artifact_used_id:
        a = conversation.last_artifact_used
        if a:
            last_artifact = {"id": a.pk, "name": a.display_name}

    return {
        "uuid": str(conversation.uuid),
        "messages": messages,
        "last_artifact_used": last_artifact,
    }


@router.post("/chat/stream/", tags=["agent/v1"])
def chat_stream(request, payload: StreamRequest):
    from ninja.errors import HttpError

    user = request.auth
    if not user or not agent_permission_policy.user_has_permission(user, "access_chatbot"):
        raise HttpError(403, "Access denied.")
    message = payload.message.strip()
    if not message:
        raise HttpError(400, "Message must not be empty.")

    if payload.artifact_id is not None:
        artifact = (
            ModelArtifact.objects.select_related("provider", "permission__content_type")
            .filter(pk=payload.artifact_id, is_active=True, provider__is_active=True)
            .first()
        )
        if artifact is None:
            raise HttpError(404, "Model not found.")
    else:
        try:
            agent_settings = AgentSiteSetting.for_request(request)
        except Exception:
            agent_settings = None
        default_pk = (
            agent_settings.default_artifact_id if agent_settings and agent_settings.default_artifact_id else None
        )
        artifact = (
            ModelArtifact.objects.select_related("provider", "permission__content_type")
            .filter(pk=default_pk, is_active=True, provider__is_active=True)
            .first()
            if default_pk
            else None
        )
        if artifact is None:
            raise HttpError(400, "No default model configured. Please select a model.")

    if artifact.permission:
        ct = artifact.permission.content_type
        perm = f"{ct.app_label}.{artifact.permission.codename}"
        if not user.has_perm(perm):
            raise HttpError(403, "You do not have access to this model.")

    env_var = artifact.provider.api_key_env_var
    if env_var and not os.environ.get(env_var):
        raise HttpError(
            400,
            f"No API key configured for {artifact.provider.display_name}. Set {env_var} in the environment.",
        )

    if payload.conversation_uuid:
        try:
            conversation = Conversation.objects.get(uuid=payload.conversation_uuid, user=user)
        except Conversation.DoesNotExist:
            raise HttpError(404, "Conversation not found.")
    else:
        conversation = Conversation.objects.create(user=user)

    return StreamingHttpResponse(
        _stream_turn_sync(conversation.pk, message, artifact.pk),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
