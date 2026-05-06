"""Agent chat endpoint — /api/agent/v1/chat/stream/"""

from __future__ import annotations

import asyncio
import json
import queue
import re
import threading
from collections.abc import AsyncIterable
from typing import Any

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from ninja import Router, Schema
from pydantic_ai import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    RunContext,
    TextPartDelta,
)
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from phoxtail.agent.llm import get_agent
from phoxtail.agent.models import Conversation
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


async def _run_turn(conversation_pk: int, user_text: str, out: queue.Queue) -> None:
    conversation = await sync_to_async(Conversation.objects.get)(pk=conversation_pk)
    history = ModelMessagesTypeAdapter.validate_python(conversation.message_history)
    agent = get_agent()
    aq: asyncio.Queue[Any] = asyncio.Queue()
    text_sent = False
    # Stash tool-call args keyed by tool_call_id so we can extract page_id on result.
    _pending_args: dict[str, dict[str, Any]] = {}
    # Accumulates streamed text so we can persist a partial response on cancellation.
    _partial_text: list[str] = []

    async def handler(ctx: RunContext, events: AsyncIterable) -> None:
        nonlocal text_sent
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                _pending_args[event.tool_call_id] = event.part.args_as_dict()
                await aq.put(("tool_start", event.part.tool_name))
            elif isinstance(event, FunctionToolResultEvent):
                tool_name = event.result.tool_name
                kind = _BLOCK_WRITE_TOOLS.get(tool_name)
                if kind is not None:
                    args = _pending_args.get(event.tool_call_id, {})
                    page_id = args.get("page_id")
                    if page_id is not None:
                        if kind == "publish":
                            # No per-block UUIDs — full-body refresh.
                            # Only emit if the publish succeeded (no error envelope).
                            try:
                                result_content = (
                                    str(event.result.content)
                                    if hasattr(event.result, "content")
                                    else ""
                                )
                                if "error" not in json.loads(result_content):
                                    await aq.put(
                                        ("blocks_changed", int(page_id), [], kind)
                                    )
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
                                result_content = (
                                    str(event.result.content)
                                    if hasattr(event.result, "content")
                                    else ""
                                )
                                changed = json.loads(result_content).get(
                                    "_changed_blocks"
                                )
                                if changed:
                                    await aq.put(
                                        ("blocks_changed", int(page_id), changed, kind)
                                    )
                            except (
                                json.JSONDecodeError,
                                AttributeError,
                                TypeError,
                                ValueError,
                            ):
                                pass
                await aq.put(("tool_end", tool_name))
            elif isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if event.part.content:
                    text_sent = True
                    _partial_text.append(event.part.content)
                    await aq.put(("token", event.part.content))
            elif isinstance(event, PartDeltaEvent) and isinstance(
                event.delta, TextPartDelta
            ):
                if event.delta.content_delta:
                    text_sent = True
                    _partial_text.append(event.delta.content_delta)
                    await aq.put(("token", event.delta.content_delta))

    async def produce() -> None:
        nonlocal text_sent
        try:
            result = await agent.run(
                user_text,
                message_history=history,
                event_stream_handler=handler,
            )
            # Fallback: if no token events fired, emit the full output now
            if not text_sent and result.output:
                _partial_text.append(str(result.output))
                await aq.put(("token", str(result.output)))

            updated = history + list(result.new_messages())
            conversation.message_history = ModelMessagesTypeAdapter.dump_python(
                updated, mode="json"
            )
            await sync_to_async(conversation.save)(
                update_fields=["message_history", "updated_at"]
            )
            if not conversation.title:
                stripped = _CONTEXT_STRIP.sub("", user_text).strip()
                if stripped:
                    conversation.title = stripped[:80]
                    await sync_to_async(conversation.save)(
                        update_fields=["title", "updated_at"]
                    )
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
            conversation.message_history = ModelMessagesTypeAdapter.dump_python(
                updated, mode="json"
            )
            await sync_to_async(conversation.save)(
                update_fields=["message_history", "updated_at"]
            )
            if not conversation.title:
                stripped = _CONTEXT_STRIP.sub("", user_text).strip()
                if stripped:
                    conversation.title = stripped[:80]
                    await sync_to_async(conversation.save)(
                        update_fields=["title", "updated_at"]
                    )
        except Exception:
            pass

    producer = asyncio.create_task(produce())
    try:
        while True:
            item = await aq.get()
            if item is _SENTINEL:
                break
            kind, *rest = item
            if kind == "token":
                out.put(_sse("token", {"text": rest[0]}))
            elif kind == "tool_start":
                out.put(_sse("tool_start", {"name": rest[0]}))
            elif kind == "tool_end":
                out.put(_sse("tool_end", {"name": rest[0]}))
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
    except Exception:
        out.put(_sse("error", {"message": "An error occurred. Please try again."}))
        raise
    finally:
        out.put(_SENTINEL)


# ── Sync streaming generator (passed to StreamingHttpResponse) ───────────────


def _stream_turn_sync(conversation_pk: int, user_text: str):
    out: queue.Queue[Any] = queue.Queue()
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(
        _run_turn(conversation_pk, user_text, out), loop
    )

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


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/conversations/{uuid}/", tags=["agent/v1"])
def get_conversation(request, uuid: str):
    from ninja.errors import HttpError

    user = request.auth
    if not user or not agent_permission_policy.user_has_permission(
        user, "access_chatbot"
    ):
        raise HttpError(403, "Access denied.")
    try:
        conversation = Conversation.objects.get(uuid=uuid, user=user)
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
            text = " ".join(p.content for p in msg.parts if isinstance(p, TextPart))
            if text:
                messages.append({"role": "assistant", "content": text})
    return {"uuid": str(conversation.uuid), "messages": messages}


@router.post("/chat/stream/", tags=["agent/v1"])
def chat_stream(request, payload: StreamRequest):
    from ninja.errors import HttpError

    user = request.auth
    if not user or not agent_permission_policy.user_has_permission(
        user, "access_chatbot"
    ):
        raise HttpError(403, "Access denied.")
    message = payload.message.strip()
    if not message:
        raise HttpError(400, "Message must not be empty.")

    if payload.conversation_uuid:
        try:
            conversation = Conversation.objects.get(
                uuid=payload.conversation_uuid, user=user
            )
        except Conversation.DoesNotExist:
            raise HttpError(404, "Conversation not found.")
    else:
        conversation = Conversation.objects.create(user=user)

    return StreamingHttpResponse(
        _stream_turn_sync(conversation.pk, message),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
