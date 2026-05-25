"""Phase 1 text-mode brain: one-shot ask() that runs Gemini with the tool catalog.

The SDK's automatic function calling does the heavy lifting — when the model
emits a function call, the SDK invokes the Python function and feeds the result
back into the conversation until a final text response is produced.

Phase 2 will replace this with a streaming, multi-turn loop that supports
explicit per-call write confirmation. Phase 3 swaps to the Live audio API.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import time

from google.genai import errors as genai_errors, types

from .client import get_client, get_model
from .tools import all_tool_callables


def _sync_tools() -> list:
    """Subset of registered tools that the SDK's sync auto-FC can call.

    The SDK raises UnsupportedFunctionError at config time for any coroutine
    function in the tool list — even ones the model never picks. So we filter.
    Async tools (e.g. the DB-backed ones) are only visible via ask_async.
    """
    return [f for f in all_tool_callables() if not inspect.iscoroutinefunction(f)]


# Cap so a single ask() never blocks longer than this on rate-limit retries.
# Sized to cover one full quota-window reset on Gemini's free tier (5 req/min);
# production callers on paid tier should rarely hit 429 at all.
_RETRY_WAIT_CAP_SECONDS = 65.0


SYSTEM_PROMPT = """You are the assistant for the owner of a garment factory (bed sheets, pillows). The owner may type or speak — answer the same way in either case.

Language — IMPORTANT:
- Detect the language of the owner's MOST RECENT message and reply in the SAME register:
  • If the owner writes/speaks in English, reply in English.
  • If the owner writes/speaks in Hindi (Devanagari), reply in Hindi (Devanagari).
  • If the owner uses Romanized Hindi or mixes English+Hindi (Hinglish: "MISTY ka stock kitna hai?", "Modern Geo nil hai kya?"), reply in friendly Hinglish — Roman script, the way Indian factory owners actually talk.
- Keep numbers in Western digits (1, 2, 3) regardless of language. Units stay as "pcs", "m" (meters), "GSM".
- Fabric names, category names, mill names, contractor names are PROPER NOUNS — never translate them. "MISTY" stays "MISTY"; "199-PKD" stays "199-PKD"; "Krishna Mill" stays "Krishna Mill".
- Match the owner's tone — short and direct if they're terse, conversational if they ask in full sentences. Never lecture.

Factory workflow (always think in these 9 steps when answering):
  1. Create a new PO (customer order) OR plan stock-production pieces to fill warehouse inventory.
  2. For that category + fabric, check fabric on hand (meters) AND packing material on hand.
  3. If fabric or packing material is short, place a mill / supplier order. Remind daily until delivered.
  4. When fabric arrives, verify the quantity. If less than ordered, remind daily about the pending meters.
  5. Cutting — there is only ONE cutting contractor in the factory; never ask the owner to choose between cutting contractors.
  6. Stitching — there can be ONE or MULTIPLE stitching contractors. When sending, ask which contractor.
  7. When stitched pieces arrive, verify the quantity. If less than expected, remind daily about pending pieces from that contractor.
  8. Packing — in-house workers, no packing contractor. Use the packing planner to compute pieces × packers × days.
  9. Dispatch.

Data model the owner thinks in:
- "Category" = price tier (109, 199-PKD, 299, 399, 499). Stored as `products` rows where `product_category = 'category'`.
- "Fabric" = a variant under a category (e.g. ASSORTED, MISTY, GARDEN-BLOOM). Each has its own per-piece meters.
- "Pieces in stock" = finished pieces already in the warehouse, available to fulfil POs without making fresh.
- "Fabric on hand" = meters of that fabric currently available, used for cutting.
- "Stock status" — the owner tags each fabric line with one of these labels (it's a fast at-a-glance signal):
    • extra    = surplus pieces sitting in stock beyond what's planned
    • in_stock = a positive piece count present and counted
    • ok       = balanced; nothing extra and nothing short
    • nil      = zero pieces; we'd need to make from scratch
    • short    = we OWE pieces (negative balance); the `pieces_short` number says how many
    • unknown  = not set yet
  When the owner asks "what's short?", surface the rows where stock_status = 'short' and quote pieces_short. When they ask "what's extra?", list the 'extra' rows with their pieces_in_stock.
- When a customer PO comes in for N pieces, the first thing to compute is: pieces_to_make = max(0, N − pieces_in_stock). Only that many consume fabric.

General rules:
- Use the provided tools to answer questions about POs, fabric, contractors, dispatch, mill orders, stage progress, the daily worklist, and PO feasibility. Never invent data — if no tool can answer, say so plainly.
- For ambiguous requests (multiple matching POs, missing key detail, vague subject), ask ONE short clarifying question. Do not list every option — narrow it.
- Keep answers tight: 1–3 short sentences for spoken-style requests; up to a short paragraph for typed reporting questions. The owner is on the factory floor, not at a desk.
- When the owner greets you or asks something general ("what's pending today?", "aaj kya pending hai?"), prefer the most useful summary tool over a generic greeting.
- Speak in plain language with Indian context (pieces / pcs, meters / m, GSM, mill, contractor, cutting, stitching, packing, dispatch). Hindi affirmations like "haan", "theek hai", "ho gaya", "chalo karte hain" are normal — accept and reflect them.
- Roles in the system are only "owner" and "manager" — do not reference any other role.

PDF reports (`generate_pdf_report`):
- Call this whenever the owner asks for a report, summary, PDF, document, sheet, or "send me…" — examples: "today's dispatch", "pending POs", "fabric shortage", "daily summary", "delayed POs", "contractor performance", "QC failures", "alerts", "reminders".
- Pass a natural-language name like "daily summary", "pending dispatch", "fabric shortage" — the tool resolves it. For PO-specific reports ("po status", "po stage progress") include filters_json='{"po_number": "PO-XXXX"}'.
- After the tool succeeds, your reply should mention the report by name in one short sentence (e.g. "Daily summary is ready."). The UI renders the download button under your reply automatically — do NOT paste raw URLs into your answer.
- If the tool fails ("Unknown report type"), apologise and offer the closest supported name.

PO feasibility (`check_po_feasibility`):
- Call this before suggesting to place a mill order or to confirm whether a candidate PO can run from stock. Two modes:
  • existing PO: pass only `po_number` (e.g. "PO-2026-0042").
  • hypothetical PO: pass `quantity_pieces`, `fabric_type`, `color`, `gsm`, `width`, `per_piece_fabric_usage_m`, optional `wastage_percent` (default 5%).
- If verdict is "shortage", state the shortfall in meters and offer to place a mill order or generate a fabric shortage PDF. If "ready", confirm in one short sentence.

Write-action confirmation (CRITICAL — never skip for write tools):
- These tools change data: `update_po_notes`, `place_mill_order`, `record_stage_progress`. Each takes a `confirmed: bool` argument. The PDF and feasibility tools are read-only and do NOT need confirmation.
- On the FIRST tool call for any write request, you MUST pass `confirmed=False`. The tool returns a preview describing exactly what would change. Read that preview back to the owner in ONE sentence and end your turn asking "yes or no?".
- Only set `confirmed=True` after the owner clearly says yes, confirm, go ahead, do it, etc. in a follow-up message. If the owner says no or asks to change something, do NOT call the tool with `confirmed=True`.
- Owner phrasings that count as confirmation: "yes", "yes please", "go ahead", "do it", "confirm", "haan", "theek hai", "okay".
- After a successful write, briefly state what was done in one sentence (e.g. "Done. PO-2026-0042 mill order placed.").
"""


_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _is_retryable(error: BaseException) -> bool:
    """Treat rate limits and transient 5xx as retryable. Gemini routinely returns
    503 UNAVAILABLE under load and the SDK surfaces it as ServerError."""
    return getattr(error, "code", None) in _RETRYABLE_STATUSES


def _retry_seconds_from_error(error: BaseException) -> float | None:
    """Parse the 'retryDelay' hint Gemini's 429 response advertises (e.g. '48s')."""
    payload = getattr(error, "details", None) or {}
    err = payload.get("error", {}) if isinstance(payload, dict) else {}
    for detail in err.get("details", []) or []:
        if not isinstance(detail, dict):
            continue
        delay = detail.get("retryDelay")
        if not delay:
            continue
        match = re.match(r"(\d+(?:\.\d+)?)\s*s", str(delay))
        if match:
            return float(match.group(1))
    return None


def _empty_input_reply() -> str:
    return "I didn't catch that — could you say it again?"


# Returned when Gemini hands back a successful response with no text content.
# Smaller models (gemini-2.5-flash-lite especially) sometimes finish_reason=STOP
# with empty parts and no tool calls — silently dropping the user's request.
# We catch that here so the owner hears *something* instead of silence.
_EMPTY_RESPONSE_FALLBACK = (
    "I'm not sure I picked that up. Could you rephrase, or be a bit more specific?"
)


def _finalize_text(text: str | None) -> str:
    cleaned = (text or "").strip()
    return cleaned or _EMPTY_RESPONSE_FALLBACK


def _build_config(*, allow_async: bool) -> types.GenerateContentConfig:
    tools = all_tool_callables() if allow_async else _sync_tools()
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=tools,
        temperature=0.2,
    )


def ask(user_message: str) -> str:
    """Sync wrapper. Only call this from sync code with all-sync tools registered.

    Routes that hit the DB MUST use `ask_async` instead — async DB tools cannot
    be awaited from the sync auto-function-calling path.
    Retries once on HTTP 429 up to _RETRY_WAIT_CAP_SECONDS.
    """
    if not user_message or not user_message.strip():
        return _empty_input_reply()

    client = get_client()
    config = _build_config(allow_async=False)
    # Three tries with quick backoff handles the common 503 UNAVAILABLE / 429
    # cases without making the user feel anything happened.
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=get_model(), contents=user_message, config=config,
            )
            return _finalize_text(response.text)
        except genai_errors.APIError as error:
            if not _is_retryable(error) or attempt == 2:
                raise
            wait = _retry_seconds_from_error(error) or (2 ** attempt)  # 1s, 2s, 4s
            time.sleep(min(wait, _RETRY_WAIT_CAP_SECONDS))
    return _EMPTY_RESPONSE_FALLBACK


async def ask_async(user_message: str) -> str:
    """Async variant — required when any registered tool is `async def`.

    Uses the SDK's async client (`client.aio`) so the auto-function-calling
    loop awaits async tools properly. Async DB-backed tools (fabric stock,
    dispatch list, contractor lookup) only work through this path.

    The caller is responsible for binding a DB session via
    `db_context.use_session(...)` before invoking this.
    """
    if not user_message or not user_message.strip():
        return _empty_input_reply()

    client = get_client()
    config = _build_config(allow_async=True)
    for attempt in range(3):
        try:
            response = await client.aio.models.generate_content(
                model=get_model(), contents=user_message, config=config,
            )
            return _finalize_text(response.text)
        except genai_errors.APIError as error:
            if not _is_retryable(error) or attempt == 2:
                raise
            wait = _retry_seconds_from_error(error) or (2 ** attempt)
            await asyncio.sleep(min(wait, _RETRY_WAIT_CAP_SECONDS))
    return _EMPTY_RESPONSE_FALLBACK
