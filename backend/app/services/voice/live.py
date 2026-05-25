"""Phase 3 — Gemini Live audio session wrapper.

Wires a FastAPI WebSocket connection into a Gemini Live bidi audio session
plus a tool dispatcher. Three concurrent tasks run inside one session:

    1. ws_to_gemini  — read binary audio frames from the browser, forward as
                       send_realtime_input(audio=...) to Gemini.
    2. gemini_to_ws  — read response events from Gemini; binary audio frames
                       are forwarded to the browser; tool calls are dispatched.
    3. supervisor    — owns the asyncio task group; cancels siblings on error.

Audio formats (FIXED by Gemini Live, do not change):
    Input  (browser → backend → Gemini): 16-bit PCM, mono, 16,000 Hz, LE.
    Output (Gemini → backend → browser): 16-bit PCM, mono, 24,000 Hz, LE.

Tool calls: Live API delivers tool calls as `LiveServerToolCall` events with
function_calls. We dispatch each call against the same registry the REST path
uses (`get_tool().func`) and post the result back via `send_tool_response`.
For write tools (requires_confirmation=True) the Gemini model is expected to
already pass `confirmed=False` first per the system-prompt rules — the brain
contract is identical to the REST path.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from .brain import SYSTEM_PROMPT
from .client import get_live_client, get_live_model
from .db_context import use_session
from .tools import all_tool_callables, get_tool


logger = logging.getLogger(__name__)


# Smaller chunks keep latency low; the SDK accepts any reasonable size.
_INPUT_AUDIO_MIME = "audio/pcm;rate=16000"


def _live_config() -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(
            role="user",
            parts=[types.Part.from_text(text=SYSTEM_PROMPT)],
        ),
        tools=[types.Tool(function_declarations=_tool_declarations())],
    )


def _tool_declarations() -> list[types.FunctionDeclaration]:
    """Convert each registered Python tool into a Gemini FunctionDeclaration.

    For the Live API we have to hand-build declarations — auto-FC (which the
    REST `generate_content` path uses) is not available on Live sessions. We
    use `FunctionDeclaration.from_callable_with_api_option` so signature +
    docstring introspection matches the REST path exactly.
    """
    declarations: list[types.FunctionDeclaration] = []
    for func in all_tool_callables():
        try:
            decl = types.FunctionDeclaration.from_callable_with_api_option(
                callable=func, api_option="GEMINI_API",
            )
        except Exception as err:  # pragma: no cover -- defensive
            logger.warning("voice/live: skipping tool %s — %s", func.__name__, err)
            continue
        declarations.append(decl)
    return declarations


async def _dispatch_tool_call(call: types.FunctionCall) -> dict[str, Any]:
    """Run one tool function the model asked for and return its result dict.

    Unknown tools or runtime errors are surfaced back to the model as a result
    payload so it can apologise and recover rather than the session hanging.
    """
    name = call.name or ""
    args: dict[str, Any] = dict(call.args or {})
    spec = get_tool(name)
    if spec is None:
        return {"error": f"unknown tool: {name}"}
    try:
        if inspect.iscoroutinefunction(spec.func):
            value = await spec.func(**args)
        else:
            value = spec.func(**args)
    except Exception as exc:
        logger.exception("voice/live: tool %s raised", name)
        return {"error": f"tool {name} failed: {exc}"}
    return value if isinstance(value, dict) else {"result": value}


async def _ws_to_gemini(websocket: WebSocket, session: Any) -> None:
    """Forward browser audio frames into the Gemini Live session.

    Browser frames are binary (raw 16-bit PCM @ 16 kHz, little-endian). Text
    frames are accepted too for control messages (currently unused but kept
    so we can add 'turn end' / 'cancel' signals later without protocol churn).
    """
    while True:
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            return
        audio_bytes: bytes | None = message.get("bytes")
        text_payload: str | None = message.get("text")
        if audio_bytes:
            await session.send_realtime_input(
                audio=types.Blob(data=audio_bytes, mime_type=_INPUT_AUDIO_MIME),
            )
        elif text_payload:
            # Reserve for future control messages; ignore unknown payloads.
            try:
                event = json.loads(text_payload)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "end_of_turn":
                # Signal the model we've stopped talking so it starts responding.
                await session.send_realtime_input(audio_stream_end=True)


async def _gemini_to_ws(websocket: WebSocket, session: Any) -> None:
    """Forward Gemini audio + dispatch tool calls back to the browser.

    Audio bytes are sent as binary WS frames. Tool calls are executed and the
    result is sent back to Gemini via send_tool_response; the browser gets a
    text frame ('tool_call' + 'tool_result') for UI status indication.
    """
    async for response in session.receive():
        # 1. Audio bytes back to the browser.
        if getattr(response, "data", None):
            await websocket.send_bytes(response.data)

        # 2. Tool calls — execute and reply.
        tool_call = getattr(response, "tool_call", None)
        if tool_call and tool_call.function_calls:
            function_responses: list[types.FunctionResponse] = []
            for call in tool_call.function_calls:
                await websocket.send_text(
                    json.dumps({"type": "tool_call", "name": call.name, "args": dict(call.args or {})})
                )
                result = await _dispatch_tool_call(call)
                await websocket.send_text(
                    json.dumps({"type": "tool_result", "name": call.name, "result": result})
                )
                function_responses.append(
                    types.FunctionResponse(id=call.id, name=call.name, response=result)
                )
            await session.send_tool_response(function_responses=function_responses)

        # 3. End-of-turn / interruption signals — surface to UI for state changes.
        server_content = getattr(response, "server_content", None)
        if server_content is not None:
            if getattr(server_content, "turn_complete", False):
                await websocket.send_text(json.dumps({"type": "turn_complete"}))
            if getattr(server_content, "interrupted", False):
                await websocket.send_text(json.dumps({"type": "interrupted"}))


async def run_live_session(websocket: WebSocket, db: AsyncSession) -> None:
    """Open one Gemini Live session bound to this WebSocket + DB session.

    The DB session is bound via `use_session` so any tool the model invokes
    can read/write the owner's data through `current_session()`.

    Returns when either side disconnects or an error stops one of the pumps.
    The caller is responsible for closing the WebSocket cleanly.
    """
    client = get_live_client()
    config = _live_config()
    try:
        with use_session(db):
            async with client.aio.live.connect(model=get_live_model(), config=config) as session:
                await websocket.send_text(json.dumps({"type": "ready"}))
                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(_ws_to_gemini(websocket, session))
                        tg.create_task(_gemini_to_ws(websocket, session))
                except* WebSocketDisconnect:
                    # Browser closed — normal end-of-call, swallow.
                    pass
    except Exception as exc:  # pragma: no cover -- surface to client
        logger.exception("voice/live: session error")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
