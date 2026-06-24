from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable
from urllib.parse import quote
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contractor import Contractor
from app.models.enums import ContractorType, DispatchCostType, POStatus, StageName
from app.models.fabric import FabricMillOrder, FabricPlan, FabricReceipt
from app.models.enums import FabricMillOrderStatus, FabricPlanStatus, FabricVerificationStatus, ReceiptStatus, StageStatus
from app.models.mill_requirement import MillOrderRequirement, MillOrderRequirementStatus
from app.models.packing_material import PackingMaterialInventory
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import Reminder, ReminderPriority, ReminderStatus, ReminderType
from app.models.stage import ContractorAllocation, StageSummary
from app.schemas.stage import ContractorAllocationCreate, StageProgressCreate
from app.services.audit_service import log_audit_event
from app.schemas.dispatch import DispatchLoadCreate
from app.services.dispatch_engine import create_dispatch_load, get_dispatch_summary
from app.services.exceptions import DomainError
from app.services.operational_backfill import TERMINAL_PO_STATUSES, ensure_all_operational_data, ensure_po_operational_data
from app.services.packing_material_service import recalculate_shortage
from app.services.stage_engine import allocate_contractor, record_stage_progress
from app.services.pdf_reports.report_registry import REPORT_REGISTRY
from app.services.pdf_reports.report_schemas import ReportGenerateRequest
from app.services.pdf_reports.report_service import ReportService
from app.services.quotation_service import build_po_quotation, generate_po_quotation_pdf
from app.services.voice.artifacts import add_artifact
from app.services.voice.action_model import PendingActionSnapshot


@dataclass(frozen=True)
class DirectAssistantAnswer:
    answer: str


@dataclass
class PendingVoiceWrite:
    action_type: str
    po_number: str
    preview: str
    payload: dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: uuid4().hex)
    original_instruction: str | None = None
    missing_fields: list[str] = field(default_factory=list)


_HELP_TEXT = (
    "I can answer from live PO data: June POs, pending dispatch, delays, shortages, "
    "stage status, contractor assignment, quotations, and PDFs. Try: "
    "'Which June POs need dispatch by end June?' or 'Show shortage for PO ...'."
)

_PENDING_WRITE: dict[str, PendingVoiceWrite] = {}


def get_pending_action_snapshot() -> PendingActionSnapshot | None:
    pending = _PENDING_WRITE.get("global")
    if pending is None:
        return None
    return PendingActionSnapshot(
        action_id=pending.action_id,
        intent=pending.action_type,
        po_number=pending.po_number if pending.po_number and not pending.po_number.startswith("__") else None,
        entities=dict(pending.payload),
        missing_fields=list(pending.missing_fields),
        confirmation_message=pending.preview or None,
    )


async def answer_factory_question(db: AsyncSession, message: str) -> DirectAssistantAnswer | None:
    text = message.strip()
    if not text:
        return DirectAssistantAnswer("I didn't catch that. Please type the PO question again.")
    normalized = _normalize(text)
    await ensure_all_operational_data(db)
    pos = await _load_pos(db)

    write_answer = await _handle_voice_write_intent(db, pos, text, normalized)
    if write_answer is not None:
        return write_answer

    if _is_greeting(normalized):
        return DirectAssistantAnswer("Hi. " + _HELP_TEXT)
    if "what can you do" in normalized or normalized in {"help", "help me"} or "help me with po status" in normalized:
        return DirectAssistantAnswer(_HELP_TEXT)

    pdf_answer = await _maybe_generate_pdf(db, normalized, pos)
    if pdf_answer is not None:
        return DirectAssistantAnswer(pdf_answer)

    quotation_answer = await _maybe_answer_quotation(db, normalized, text, pos)
    if quotation_answer is not None:
        return DirectAssistantAnswer(quotation_answer)

    if "biggest risk" in normalized or "focus on today" in normalized or "which po should i focus" in normalized:
        return DirectAssistantAnswer(_biggest_risk(pos))
    if "contractor" in normalized and "delayed" in normalized:
        return DirectAssistantAnswer(await _list_delayed_contractors(db))
    if "show mill invoice" in normalized or "show mill invoices" in normalized or "mill invoice" in normalized or "fabric invoice" in normalized:
        return DirectAssistantAnswer(await _list_mill_invoices(db))
    if "mill order" in normalized or "mill purchase" in normalized or "needs mill order" in normalized or "need mill order" in normalized:
        po = _extract_po(pos, text)
        if po is not None:
            return DirectAssistantAnswer(_po_mill_requirement(po))
        return DirectAssistantAnswer(_list_mill_requirements(pos))
    if _mentions_packing_material(normalized):
        return DirectAssistantAnswer(await _list_packing_materials_for_owner(db, pos, text, normalized))

    rate_answer = _answer_price_or_rate_query(pos, normalized)
    if rate_answer is not None:
        return DirectAssistantAnswer(rate_answer)

    po = _extract_po(pos, text)
    if po is not None:
        return DirectAssistantAnswer(await _answer_specific_po(db, po, normalized))

    if "today" in normalized and ("summary" in normalized or "attention" in normalized or "focus" in normalized):
        return DirectAssistantAnswer(_factory_summary(pos))
    if "what should i show" in normalized and "owner" in normalized:
        return DirectAssistantAnswer(_owner_demo_talking_points(pos))
    if "fabric ordered but not received" in normalized or "fabric orderd but not received" in normalized or "ordered but not received" in normalized:
        return DirectAssistantAnswer(_list_ordered_not_received(pos))
    if "fabric ready" in normalized or "has fabric ready" in normalized or "fabric is ready" in normalized:
        return DirectAssistantAnswer(_list_fabric_ready(pos))
    if "due this week" in normalized or "due in this week" in normalized or "due today" in normalized:
        return DirectAssistantAnswer(_list_due_this_week(pos))
    if "king size" in normalized or "king-size" in normalized or "king bed" in normalized:
        return DirectAssistantAnswer(_answer_king_fabric_requirement(pos))

    if "june" in normalized or "end of june" in normalized or "june end" in normalized:
        return DirectAssistantAnswer(_answer_june_query(pos, normalized))

    if "fabric shortage" in normalized or "have shortage" in normalized or "shortage" in normalized:
        return DirectAssistantAnswer(_list_shortages(pos))
    if "ready for dispatch" in normalized or "ready-to-dispatch" in normalized or "dispatch ready" in normalized:
        return DirectAssistantAnswer(_list_dispatch_ready(pos))
    if "pending dispatch" in normalized or "show pending dispatch" in normalized:
        return DirectAssistantAnswer(_list_pending_dispatch(pos))
    if "delayed" in normalized or "missed dispatch" in normalized:
        return DirectAssistantAnswer(_list_delayed(pos))
    if "stuck in cutting" in normalized or "cutting status" in normalized:
        return DirectAssistantAnswer(_list_stage_pending(pos, StageName.cutting, "cutting"))
    if "stuck in stitching" in normalized or "stitching status" in normalized:
        return DirectAssistantAnswer(_list_stage_pending(pos, StageName.stitching, "stitching"))
    if "in finishing" in normalized or "finishing status" in normalized:
        return DirectAssistantAnswer(_list_stage_pending(pos, StageName.quality_check, "finishing/quality check"))

    return None


async def _load_pos(db: AsyncSession) -> list[PurchaseOrder]:
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
            selectinload(PurchaseOrder.dispatch_loads),
        )
        .order_by(PurchaseOrder.promise_delivery_date.asc(), PurchaseOrder.po_number.asc())
    )
    return list(result.scalars().all())


async def _handle_voice_write_intent(
    db: AsyncSession,
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
) -> DirectAssistantAnswer | None:
    if _is_confirm(normalized):
        pending = _PENDING_WRITE.pop("global", None)
        if pending is None:
            return DirectAssistantAnswer("There is no pending update to confirm.")
        if pending.missing_fields:
            _PENDING_WRITE["global"] = pending
            return DirectAssistantAnswer(_missing_field_question(pending))
        return DirectAssistantAnswer(await _execute_pending_write(db, pending))
    if _is_cancel(normalized):
        pending = _PENDING_WRITE.pop("global", None)
        if pending is None:
            return DirectAssistantAnswer("No pending update was active.")
        return DirectAssistantAnswer(f"Cancelled. I did not update {pending.po_number}.")

    followup = _try_complete_pending_action(pos, raw_text, normalized)
    if followup is not None:
        return followup

    preview = _parse_voice_write(pos, raw_text, normalized)
    if isinstance(preview, DirectAssistantAnswer):
        return preview
    if preview is None:
        return None
    _PENDING_WRITE["global"] = preview
    if preview.missing_fields:
        return DirectAssistantAnswer(_missing_field_question(preview))
    return DirectAssistantAnswer(_confirmation_prompt(preview))


def _try_complete_pending_action(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
) -> DirectAssistantAnswer | None:
    pending = _PENDING_WRITE.get("global")
    if pending is None or not pending.missing_fields:
        return None
    if _looks_like_new_action(normalized):
        _PENDING_WRITE.pop("global", None)
        return None

    po = _extract_po(pos, raw_text)
    if po is not None:
        pending.po_number = po.po_number
        pending.payload["po_number"] = po.po_number

    meters = _extract_meters(normalized)
    if meters is not None:
        pending.payload["meters"] = str(meters)

    pieces = _extract_pieces(normalized)
    if pieces is not None:
        pending.payload["pieces"] = int(pieces)

    mill_name = _extract_mill_name(raw_text)
    if mill_name is not None:
        pending.payload["mill_name"] = mill_name

    contractor_name = _extract_contractor_name(raw_text)
    if contractor_name is not None:
        pending.payload["contractor_name"] = contractor_name

    delivery_date = _extract_date(raw_text, normalized)
    if delivery_date is not None:
        pending.payload["date"] = delivery_date.isoformat()

    _refresh_missing_fields(pending)
    if pending.missing_fields:
        return DirectAssistantAnswer(_missing_field_question(pending))
    pending.preview = _build_preview(pending)
    _PENDING_WRITE["global"] = pending
    return DirectAssistantAnswer(_confirmation_prompt(pending))


def _looks_like_new_action(normalized: str) -> bool:
    return any(
        token in normalized
        for token in (
            "dispatch",
            "fabric arrived",
            "fabric received",
            "kapda",
            "cutting",
            "stitching",
            "packing",
            "mark ",
            "update ",
            "change ",
            "complete",
        )
    )


def _refresh_missing_fields(pending: PendingVoiceWrite) -> None:
    required = _required_fields_for_action(pending.action_type)
    missing: list[str] = []
    for field_name in required:
        if field_name == "po_number":
            if not pending.po_number or pending.po_number.startswith("__"):
                missing.append(field_name)
        elif not pending.payload.get(field_name):
            missing.append(field_name)
    pending.missing_fields = missing


def _required_fields_for_action(action_type: str) -> tuple[str, ...]:
    return {
        "fabric_received": ("po_number", "meters", "mill_name"),
        "fabric_ordered": ("po_number", "meters", "mill_name"),
        "dispatch_pieces": ("po_number", "pieces"),
        "complete_stage": ("po_number", "stage", "pieces"),
        "assign_to_stitching": ("po_number", "pieces", "contractor_name"),
        "quality_quantities": ("po_number",),
        "update_delivery_date": ("po_number", "date"),
        "po_status_update": ("po_number", "status"),
        "mark_completed": ("po_number",),
    }.get(action_type, ())


def _missing_field_question(pending: PendingVoiceWrite) -> str:
    missing = set(pending.missing_fields)
    if "po_number" in missing:
        return "Which PO should I update?"
    if pending.action_type in {"fabric_received", "fabric_ordered"}:
        if {"meters", "mill_name"}.issubset(missing):
            return f"How many meters, and from which mill, for {pending.po_number}?"
        if "meters" in missing:
            return f"How many meters for {pending.po_number}?"
        if "mill_name" in missing:
            return f"Which mill is this fabric from for {pending.po_number}?"
    if "pieces" in missing:
        return f"How many pieces for {pending.po_number}?"
    if "contractor_name" in missing:
        return f"Which stitching contractor should receive {pending.po_number}?"
    if "date" in missing:
        return f"What date should I set for {pending.po_number}?"
    return "I need one more detail before I can update it."


def _confirmation_prompt(pending: PendingVoiceWrite) -> str:
    return f"Confirm: {pending.preview}? Say yes to confirm, or no to cancel."


def _build_preview(pending: PendingVoiceWrite) -> str:
    if pending.action_type == "fabric_received":
        return f"receive {pending.payload['meters']} meters from {pending.payload['mill_name']} for {pending.po_number} today"
    if pending.action_type == "fabric_ordered":
        return f"record fabric ordered for {pending.po_number}, {pending.payload['meters']} meters from {pending.payload['mill_name']}"
    if pending.action_type == "dispatch_pieces":
        return f"dispatch {pending.payload['pieces']} pieces for {pending.po_number} today"
    if pending.action_type == "complete_stage":
        return f"mark {pending.payload['stage'].replace('_', ' ')} complete for {pending.payload['pieces']} pieces of {pending.po_number}"
    if pending.action_type == "assign_to_stitching":
        return f"send {pending.payload['pieces']} pieces of {pending.po_number} to {pending.payload['contractor_name']} for stitching"
    if pending.action_type == "quality_quantities":
        parts = []
        if int(pending.payload.get("repair_pieces") or 0):
            parts.append(f"{pending.payload['repair_pieces']} repair")
        if int(pending.payload.get("alteration_pieces") or 0):
            parts.append(f"{pending.payload['alteration_pieces']} alteration")
        if int(pending.payload.get("rejected_pieces") or 0):
            parts.append(f"{pending.payload['rejected_pieces']} rejected")
        return f"record {' and '.join(parts)} pieces for {pending.po_number}"
    if pending.action_type == "update_delivery_date":
        return f"update shipment date of {pending.po_number} to {pending.payload['date']}"
    if pending.action_type == "mark_completed":
        warning = pending.payload.get("warning")
        return f"mark {pending.po_number} completed{f' ({warning})' if warning else ''}"
    return pending.preview


def _parse_voice_write(pos: list[PurchaseOrder], raw_text: str, normalized: str) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    explicit_write = any(word in normalized for word in ("update", "record", "log ", "mark ", "move ", "moved ", "set ", "change ", "kar do", "kardo"))
    if normalized.startswith(("dispatch ", "ship ", "send ")):
        explicit_write = True
    has_meters = _extract_meters(normalized) is not None
    starts_like_question = normalized.startswith(("which ", "what ", "show ", "any ", "how ", "is ", "are "))
    if starts_like_question and not explicit_write and not has_meters:
        return None

    is_fabric_order = (
        ("fabric" in normalized or "kapda" in normalized)
        and any(word in normalized for word in ("ordered", "orderd", "order placed", "order "))
        and not any(word in normalized for word in ("received", "recieved", "arrived", "aa gaya", "aagaya"))
    )
    is_fabric_received = (
        ("fabric" in normalized or "kapda" in normalized)
        and any(word in normalized for word in ("received", "recieved", "arrived", "arrival", "aa gaya", "aagaya", "receive ho gaya"))
    )
    is_dispatch_update = any(word in normalized for word in ("dispatched", "dispatch", "shipped", "ship ")) and _extract_pieces(normalized) is not None
    stage = _stage_from_text(normalized)
    is_stage_update = stage is not None and (explicit_write or any(word in normalized for word in ("stage", "status", "in ", "on ")))

    packing_material_update = _parse_packing_material_update(pos, raw_text, normalized, explicit_write)
    if packing_material_update is not None:
        return packing_material_update

    if is_dispatch_update:
        pieces = _extract_pieces(normalized)
        matches = _match_update_targets(pos, raw_text, normalized, str(pieces or ""))
        if not matches:
            return DirectAssistantAnswer("Please tell me the PO number or exact price-rate category before I record dispatch.")
        if len(matches) > 1:
            preview = ", ".join(po.po_number for po in matches[:5])
            return DirectAssistantAnswer(f"I found {len(matches)} matching POs: {preview}. Which exact PO should I update?")
        po = matches[0]
        return PendingVoiceWrite(
            action_type="dispatch_pieces",
            po_number=po.po_number,
            preview=f"record {pieces} pieces dispatched for {po.po_number} today",
            payload={"pieces": int(pieces or 0)},
        )

    po_status_update = _parse_po_status_update(pos, raw_text, normalized, explicit_write)
    if po_status_update is not None:
        return po_status_update

    data_update = _parse_voice_data_update(pos, raw_text, normalized, explicit_write)
    if data_update is not None:
        return data_update

    if not (is_fabric_order or is_fabric_received or is_stage_update):
        delivery_update = _parse_delivery_date_update(pos, raw_text, normalized, explicit_write)
        if delivery_update is not None:
            return delivery_update
        completion = _parse_completion_update(pos, raw_text, normalized)
        if completion is not None:
            return completion
        assignment = _parse_stitching_assignment(pos, raw_text, normalized)
        if assignment is not None:
            return assignment
        quality = _parse_quality_quantity_update(pos, raw_text, normalized)
        if quality is not None:
            return quality
        dispatch_without_qty = _parse_dispatch_without_quantity(pos, raw_text, normalized)
        if dispatch_without_qty is not None:
            return dispatch_without_qty
        return None

    po = _extract_po(pos, raw_text)

    if is_fabric_order:
        meters = _extract_meters(normalized)
        mill_name = _extract_mill_name(raw_text)
        pending = PendingVoiceWrite(
            action_type="fabric_ordered",
            po_number=po.po_number if po is not None else "__missing_po__",
            preview="",
            payload={"meters": str(meters) if meters is not None else None, "mill_name": mill_name if mill_name else None},
            original_instruction=raw_text,
        )
        _refresh_missing_fields(pending)
        if not pending.missing_fields:
            pending.preview = _build_preview(pending)
        return pending

    if is_fabric_received:
        meters = _extract_meters(normalized)
        mill_name = _extract_mill_name(raw_text)
        pending = PendingVoiceWrite(
            action_type="fabric_received",
            po_number=po.po_number if po is not None else "__missing_po__",
            preview="",
            payload={"meters": str(meters) if meters is not None else None, "mill_name": mill_name},
            original_instruction=raw_text,
        )
        _refresh_missing_fields(pending)
        if not pending.missing_fields:
            pending.preview = _build_preview(pending)
        return pending

    if is_stage_update and stage is not None:
        if po is None:
            return DirectAssistantAnswer("Please tell me the PO number before I update the stage.")
        return PendingVoiceWrite(
            action_type="stage_update",
            po_number=po.po_number,
            preview=f"move {po.po_number} to {stage.value.replace('_', ' ')} stage",
            payload={"stage": stage.value},
        )
    return None


def _parse_dispatch_without_quantity(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if not any(token in normalized for token in ("went for dispatch", "gone for dispatch", "dispatch mein", "dispatch me", "dispatch chala", "for dispatch")):
        return None
    po = _extract_po(pos, raw_text)
    if po is None:
        return DirectAssistantAnswer("Which PO went for dispatch?")
    ready = _dispatch_ready_qty(po)
    if ready <= 0:
        return DirectAssistantAnswer(f"{po.po_number} does not show any dispatch-ready pieces. How many pieces were dispatched?")
    return PendingVoiceWrite(
        action_type="dispatch_pieces",
        po_number=po.po_number,
        preview=f"dispatch {ready} pieces for {po.po_number} today",
        payload={"pieces": ready},
        original_instruction=raw_text,
    )


def _parse_completion_update(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if not any(token in normalized for token in ("complete", "completed", "ho gayi", "ho gaya", "done")):
        return None
    stage = _stage_from_text(normalized)
    if stage not in {StageName.cutting, StageName.packing}:
        return None
    po = _extract_po(pos, raw_text)
    if po is None:
        return DirectAssistantAnswer(f"Which PO is {stage.value.replace('_', ' ')} completed for?")
    pieces = _extract_pieces(normalized)
    if pieces is None:
        summary = next((row for row in po.stage_summaries if row.stage == stage), None)
        pieces = int(summary.pending_qty if summary and summary.pending_qty > 0 else po.order_quantity_pcs)
    pending = PendingVoiceWrite(
        action_type="complete_stage",
        po_number=po.po_number,
        preview="",
        payload={"stage": stage.value, "pieces": int(pieces)},
        original_instruction=raw_text,
    )
    _refresh_missing_fields(pending)
    if not pending.missing_fields:
        pending.preview = _build_preview(pending)
    return pending


def _extract_contractor_name(raw_text: str) -> str | None:
    cleaned = raw_text.strip()
    patterns = (
        r"\bto\s+([A-Za-z][A-Za-z0-9 .&'-]{1,80}?)(?:\s+(?:stitching|contractor|factor|factors))?(?:[.,]|$)",
        r"\bko\s+([A-Za-z][A-Za-z0-9 .&'-]{1,80}?)(?:\s+(?:stitching|contractor|factor|factors))?(?:[.,]|$)",
        r"\b([A-Za-z][A-Za-z0-9 .&'-]{1,80}?\s+(?:contractor|factors|factor))\b",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            name = re.sub(r"\s+", " ", match.group(1)).strip(" .,-")
            name = re.sub(r"\b(stitching|contractor)\b", "", name, flags=re.IGNORECASE).strip(" .,-")
            return name or None
    return None


def _parse_stitching_assignment(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if "stitch" not in normalized and "silai" not in normalized:
        return None
    if not any(token in normalized for token in ("send", "bhej", "bhejo", "assign", "allocate", "to ")):
        return None
    po = _extract_po(pos, raw_text)
    pieces = _extract_pieces(normalized)
    contractor_name = _extract_contractor_name(raw_text)
    pending = PendingVoiceWrite(
        action_type="assign_to_stitching",
        po_number=po.po_number if po is not None else "__missing_po__",
        preview="",
        payload={"pieces": pieces, "contractor_name": contractor_name},
        original_instruction=raw_text,
    )
    _refresh_missing_fields(pending)
    if not pending.missing_fields:
        pending.preview = _build_preview(pending)
    return pending


def _extract_quantity_before_word(normalized: str, aliases: Iterable[str]) -> int | None:
    for alias in aliases:
        pattern = rf"\b(\d[\d,]*)\s*(?:pcs|piece|pieces)?\s+(?:in\s+)?{re.escape(alias)}\b"
        match = re.search(pattern, normalized)
        if match:
            return int(match.group(1).replace(",", ""))
    for alias in aliases:
        pattern = rf"\b{re.escape(alias)}\s+(?:is\s+|mein\s+|me\s+)?(\d[\d,]*)\b"
        match = re.search(pattern, normalized)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def _parse_quality_quantity_update(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if not any(token in normalized for token in ("repair", "alteration", "alter ", "rejected", "reject")):
        return None
    repair = _extract_quantity_before_word(normalized, ("repair",))
    alter = _extract_quantity_before_word(normalized, ("alteration", "alter"))
    rejected = _extract_quantity_before_word(normalized, ("rejected", "reject"))
    if not any((repair, alter, rejected)):
        return None
    po = _extract_po(pos, raw_text)
    pending = PendingVoiceWrite(
        action_type="quality_quantities",
        po_number=po.po_number if po is not None else "__missing_po__",
        preview="",
        payload={
            "repair_pieces": int(repair or 0),
            "alteration_pieces": int(alter or 0),
            "rejected_pieces": int(rejected or 0),
        },
        original_instruction=raw_text,
    )
    _refresh_missing_fields(pending)
    if not pending.missing_fields:
        pending.preview = _build_preview(pending)
    return pending


def _extract_date(raw_text: str, normalized: str) -> date | None:
    today = date.today()
    if "today" in normalized or "aaj" in normalized:
        return today
    if "tomorrow" in normalized or "kal" in normalized:
        return today + timedelta(days=1)

    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", normalized)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    months = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }
    day_month = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+(20\d{2}))?\b", raw_text, flags=re.IGNORECASE)
    if day_month:
        month = months.get(day_month.group(2).lower())
        if month:
            try:
                return date(int(day_month.group(3) or today.year), month, int(day_month.group(1)))
            except ValueError:
                return None
    month_day = re.search(r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(20\d{2}))?\b", raw_text, flags=re.IGNORECASE)
    if month_day:
        month = months.get(month_day.group(1).lower())
        if month:
            try:
                return date(int(month_day.group(3) or today.year), month, int(month_day.group(2)))
            except ValueError:
                return None
    return None


def _parse_delivery_date_update(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
    explicit_write: bool,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if not explicit_write and "date" not in normalized:
        return None
    if not any(token in normalized for token in ("date", "shipment", "delivery")):
        return None
    parsed = _extract_date(raw_text, normalized)
    po = _extract_po(pos, raw_text)
    pending = PendingVoiceWrite(
        action_type="update_delivery_date",
        po_number=po.po_number if po is not None else "__missing_po__",
        preview="",
        payload={"date": parsed.isoformat() if parsed else None},
        original_instruction=raw_text,
    )
    _refresh_missing_fields(pending)
    if not pending.missing_fields:
        pending.preview = _build_preview(pending)
    return pending


async def _execute_pending_write(db: AsyncSession, pending: PendingVoiceWrite) -> str:
    if pending.action_type == "bulk_data_update":
        return await _execute_bulk_data_update(db, pending)
    if pending.action_type == "packing_material_update":
        return await _execute_packing_material_update(db, pending)
    po = await _load_po_by_number(db, pending.po_number)
    if po is None:
        return f"I could not find {pending.po_number}, so nothing was updated."
    if pending.action_type == "fabric_ordered":
        return await _execute_fabric_ordered(db, po, pending)
    if pending.action_type == "fabric_received":
        return await _execute_fabric_received(db, po, pending)
    if pending.action_type == "stage_update":
        return await _execute_stage_update(db, po, pending)
    if pending.action_type == "dispatch_pieces":
        return await _execute_dispatch_pieces(db, po, pending)
    if pending.action_type == "po_status_update":
        return await _execute_po_status_update(db, po, pending)
    if pending.action_type == "mark_completed":
        return await _execute_mark_completed(db, po, pending)
    if pending.action_type == "complete_stage":
        return await _execute_complete_stage(db, po, pending)
    if pending.action_type == "assign_to_stitching":
        return await _execute_assign_to_stitching(db, po, pending)
    if pending.action_type == "quality_quantities":
        return await _execute_quality_quantities(db, po, pending)
    if pending.action_type == "update_delivery_date":
        return await _execute_update_delivery_date(db, po, pending)
    return "I could not understand the pending update, so nothing was changed."


_PO_UPDATE_FIELDS: dict[str, dict[str, Any]] = {
    "selling_price": {
        "label": "selling price",
        "scope": "purchase_order",
        "type": "decimal",
        "synonyms": ("selling price", "selling rate", "sale price", "sales price", "price", "rate"),
    },
    "mrp": {
        "label": "MRP",
        "scope": "purchase_order",
        "type": "decimal",
        "synonyms": ("mrp", "mrp price", "package price"),
    },
    "order_quantity_pcs": {
        "label": "order quantity",
        "scope": "purchase_order",
        "type": "int",
        "synonyms": ("quantity", "qty", "pieces", "order quantity"),
    },
}

_PRODUCT_UPDATE_FIELDS: dict[str, dict[str, Any]] = {
    "gsm": {
        "label": "GSM",
        "scope": "product",
        "type": "decimal",
        "synonyms": ("gsm",),
    },
    "width": {
        "label": "fabric width",
        "scope": "product",
        "type": "decimal",
        "synonyms": ("width", "fabric width"),
    },
    "per_piece_fabric_usage_m": {
        "label": "meter per piece",
        "scope": "product",
        "type": "decimal",
        "synonyms": (
            "meter per piece",
            "metre per piece",
            "meters per piece",
            "meter per pcs",
            "meter pr pcs",
            "mtr per pcs",
            "per piece consumption",
            "per pcs consumption",
            "piece consumption",
            "fabric consumption",
            "consumption",
            "meter usage",
            "fabric usage",
        ),
    },
    "wastage_percent": {
        "label": "wastage percent",
        "scope": "product",
        "type": "decimal",
        "synonyms": ("wastage", "wastage percent", "wastage percentage"),
    },
    "size": {
        "label": "size",
        "scope": "product",
        "type": "text",
        "synonyms": ("size", "product size"),
    },
    "fabric_type": {
        "label": "fabric type",
        "scope": "product",
        "type": "text",
        "synonyms": ("fabric type", "fabric"),
    },
}


def _parse_voice_data_update(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
    explicit_write: bool,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if not explicit_write:
        return None
    field_name, spec = _extract_update_field(normalized)
    if field_name is None or spec is None:
        return None
    value = _extract_update_value(raw_text, normalized, spec)
    if value is None:
        return DirectAssistantAnswer(f"What value should I set for {spec['label']}?")
    matches = _match_update_targets(pos, raw_text, normalized, str(value))
    if not matches:
        return DirectAssistantAnswer(
            f"I could not find matching POs for this update. Please mention a PO number or a category/rate like 69."
        )
    preview_pos = ", ".join(po.po_number for po in matches[:6])
    if len(matches) > 6:
        preview_pos += f", and {len(matches) - 6} more"
    return PendingVoiceWrite(
        action_type="bulk_data_update",
        po_number=f"{len(matches)} POs",
        preview=f"set {spec['label']} to {_display_update_value(value, spec)} for {len(matches)} PO(s): {preview_pos}",
        payload={
            "field": field_name,
            "label": spec["label"],
            "scope": spec["scope"],
            "type": spec["type"],
            "value": str(value),
            "po_numbers": [po.po_number for po in matches],
        },
    )


def _extract_update_field(normalized: str) -> tuple[str | None, dict[str, Any] | None]:
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for field, spec in {**_PO_UPDATE_FIELDS, **_PRODUCT_UPDATE_FIELDS}.items():
        for synonym in spec["synonyms"]:
            if synonym in normalized:
                candidates.append((len(synonym), field, spec))
    if candidates:
        _, field, spec = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
        return field, spec
    return None, None


def _extract_update_value(raw_text: str, normalized: str, spec: dict[str, Any]) -> Decimal | int | str | None:
    value_type = str(spec["type"])
    label_pattern = "|".join(re.escape(synonym) for synonym in spec["synonyms"])
    if value_type in {"decimal", "int"}:
        patterns = [
            r"(?:to|with|as|at)\s*(?:rs\.?|rupees?|₹)?\s*(\d[\d,]*(?:\.\d+)?)",
            r"(?:rs\.?|rupees?|₹)\s*(\d[\d,]*(?:\.\d+)?)",
            rf"(?:{label_pattern})\s*(?:is|to|with|as|at|rs\.?|rupees?|₹)?\s*(\d[\d,]*(?:\.\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            number = match.group(1).replace(",", "")
            if value_type == "int":
                return int(Decimal(number))
            return Decimal(number)
        return None
    patterns = [
        r"(?:to|with|as)\s+(.+)$",
        rf"(?:{label_pattern})\s+(?:is|to|with|as)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip()).strip(" .")
    return None


def _match_update_targets(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
    value_text: str,
) -> list[PurchaseOrder]:
    exact_po = _extract_po(pos, raw_text)
    target_numbers = _target_numbers_for_update(normalized, value_text)
    matches: list[PurchaseOrder] = []
    if target_numbers:
        for po in pos:
            product_name = (po.product.product_name if po.product else "").lower()
            design_name = (po.design_name_snapshot or "").lower()
            design_code = (po.design_code_snapshot or "").lower()
            for number in target_numbers:
                if (
                    product_name.startswith(f"{number}-")
                    or product_name.startswith(f"{number} ")
                    or f" {number}-" in product_name
                    or design_name.startswith(f"{number}-")
                    or design_code.startswith(f"{number}-")
                    or (po.selling_price is not None and Decimal(po.selling_price) == Decimal(number))
                    or (po.mrp is not None and Decimal(po.mrp) == Decimal(number))
                ):
                    matches.append(po)
                    break
    if not matches and exact_po is not None:
        matches = [exact_po]
    # Stable order and de-duplication.
    seen = set()
    unique = []
    for po in sorted(matches, key=lambda item: item.po_number):
        if po.po_number in seen:
            continue
        seen.add(po.po_number)
        unique.append(po)
    return unique


def _target_numbers_for_update(normalized: str, value_text: str) -> list[str]:
    all_numbers = [token.replace(",", "") for token in re.findall(r"\d+(?:\.\d+)?", normalized)]
    value = str(value_text).replace(",", "").rstrip("0").rstrip(".")
    targets = []
    for token in all_numbers:
        comparable = token.rstrip("0").rstrip(".")
        if comparable == value:
            continue
        if token not in targets:
            targets.append(token)
    return targets


async def _execute_bulk_data_update(db: AsyncSession, pending: PendingVoiceWrite) -> str:
    field = str(pending.payload["field"])
    scope = str(pending.payload["scope"])
    value_type = str(pending.payload["type"])
    value = _coerce_update_value(str(pending.payload["value"]), value_type)
    po_numbers = list(pending.payload.get("po_numbers") or [])
    if not po_numbers:
        return "No PO targets were saved for this update, so nothing was changed."

    result = await db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_number.in_(po_numbers))
        .options(selectinload(PurchaseOrder.product))
        .order_by(PurchaseOrder.po_number.asc())
    )
    pos = list(result.scalars().all())
    if not pos:
        return "I could not find the selected POs anymore, so nothing was updated."

    updated = 0
    updated_products: set[str] = set()
    for po in pos:
        target = po if scope == "purchase_order" else po.product
        entity_type = "purchase_order" if scope == "purchase_order" else "product"
        if target is None or not hasattr(target, field):
            continue
        old_value = getattr(target, field)
        setattr(target, field, value)
        updated += 1
        if scope == "product":
            updated_products.add(str(target.id))
        if scope in {"product", "purchase_order"}:
            await ensure_po_operational_data(db, po, commit=False)
        await log_audit_event(
            db,
            action_type="voice_bulk_data_update",
            purchase_order_id=po.id,
            entity_type=entity_type,
            entity_id=str(target.id),
            old_value_json={field: _json_safe_value(old_value), "po_number": po.po_number},
            new_value_json={field: _json_safe_value(value), "po_number": po.po_number},
            remarks="Confirmed voice command.",
        )
    await db.commit()
    value_display = _display_update_value(value, {"type": value_type, "label": pending.payload["label"]})
    if scope == "product":
        return (
            f"Updated {updated} PO rows across {len(updated_products)} product record(s). "
            f"{pending.payload['label']} is now {value_display} for the selected POs."
        )
    return f"Updated {updated} PO(s). {pending.payload['label']} is now {value_display}."


def _parse_packing_material_update(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
    explicit_write: bool,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if not explicit_write or not _mentions_packing_material(normalized):
        return None
    field = _packing_material_field(normalized)
    if field is None:
        return DirectAssistantAnswer("Which packing material value should I update: required, in stock, ordered, received, consumed, or supplier?")
    material = _packing_material_name(normalized)
    if material is None:
        return DirectAssistantAnswer("Which packing material should I update: polybag, label, insert card, carton, or tape?")
    value = _extract_packing_material_value(raw_text, normalized, field)
    if value is None:
        return DirectAssistantAnswer(f"What value should I set for {material} {field.replace('_qty', '').replace('_', ' ')}?")
    matches = _match_update_targets(pos, raw_text, normalized, str(value))
    if not matches:
        return DirectAssistantAnswer("Please mention a PO number or a price-rate category like 99 before I update packing material.")
    preview_pos = ", ".join(po.po_number for po in matches[:6])
    if len(matches) > 6:
        preview_pos += f", and {len(matches) - 6} more"
    return PendingVoiceWrite(
        action_type="packing_material_update",
        po_number=f"{len(matches)} POs",
        preview=f"set {material} {field.replace('_qty', '').replace('_', ' ')} to {value} for {len(matches)} PO(s): {preview_pos}",
        payload={
            "field": field,
            "material": material,
            "value": str(value),
            "po_numbers": [po.po_number for po in matches],
        },
    )


def _parse_po_status_update(
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
    explicit_write: bool,
) -> PendingVoiceWrite | DirectAssistantAnswer | None:
    if not explicit_write or "status" not in normalized:
        return None
    if any(word in normalized for word in ("packing material", "polybag", "carton", "label", "insert", "stiffener", "bag", "tag", "header", "tape")):
        return None
    status = _po_status_from_text(normalized)
    if status is None:
        return DirectAssistantAnswer("Which PO status should I set? For example: fabric ready, stitching, packing, dispatch, completed, or shortage.")
    matches = _match_update_targets(pos, raw_text, normalized, status.value)
    if not matches:
        exact_po = _extract_po(pos, raw_text)
        matches = [exact_po] if exact_po is not None else []
    if not matches:
        return DirectAssistantAnswer("Please tell me the PO number or exact price-rate category before I update status.")
    if len(matches) > 1:
        preview = ", ".join(po.po_number for po in matches[:5])
        return DirectAssistantAnswer(f"I found {len(matches)} matching POs: {preview}. Which exact PO should I update?")
    if status == POStatus.completed:
        pending_qty = _pending_qty(matches[0])
        warning = f"{pending_qty} pieces may still be pending" if pending_qty > 0 else None
        return PendingVoiceWrite(
            action_type="mark_completed",
            po_number=matches[0].po_number,
            preview="",
            payload={"warning": warning},
        )
    return PendingVoiceWrite(
        action_type="po_status_update",
        po_number=matches[0].po_number,
        preview=f"set {matches[0].po_number} status to {status.value.replace('_', ' ')}",
        payload={"status": status.value},
    )


async def _execute_packing_material_update(db: AsyncSession, pending: PendingVoiceWrite) -> str:
    field = str(pending.payload["field"])
    material = str(pending.payload["material"])
    value = str(pending.payload["value"])
    po_numbers = list(pending.payload.get("po_numbers") or [])
    rows = await _matching_packing_material_rows(db, po_numbers, material)
    if not rows:
        return f"I could not find {material} packing material rows for the selected PO(s). Generate June materials first."
    updated = 0
    for row in rows:
        old_value = getattr(row, field)
        if field.endswith("_qty"):
            setattr(row, field, Decimal(value))
        else:
            setattr(row, field, value)
        recalculate_shortage(row)
        updated += 1
        await log_audit_event(
            db,
            action_type="voice_packing_material_update",
            purchase_order_id=row.purchase_order_id,
            entity_type="packing_material_inventory",
            entity_id=str(row.id),
            old_value_json={field: _json_safe_value(old_value), "material": row.material_name, "po_number": row.po_number},
            new_value_json={field: value, "material": row.material_name, "po_number": row.po_number},
            remarks="Confirmed voice command.",
        )
    await db.commit()
    return f"Updated {updated} packing material row(s). {material} {field.replace('_qty', '').replace('_', ' ')} is now {value}."


async def _execute_po_status_update(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    status = POStatus(str(pending.payload["status"]))
    old_status = po.status.value
    po.status = status
    stage = _stage_for_po_status(status)
    if stage is not None:
        await _set_stage_position(db, po, stage)
    await log_audit_event(
        db,
        action_type="voice_po_status_update",
        purchase_order_id=po.id,
        entity_type="purchase_order",
        entity_id=str(po.id),
        old_value_json={"status": old_status},
        new_value_json={"status": po.status.value},
        remarks="Confirmed voice command.",
    )
    await db.commit()
    return f"Updated {po.po_number}. Status is now {po.status.value.replace('_', ' ')}."


async def _list_packing_materials_for_owner(
    db: AsyncSession,
    pos: list[PurchaseOrder],
    raw_text: str,
    normalized: str,
) -> str:
    po = _extract_po(pos, raw_text)
    material = _packing_material_name(normalized)
    stmt = select(PackingMaterialInventory).order_by(PackingMaterialInventory.po_number.asc(), PackingMaterialInventory.material_name.asc())
    if po is not None:
        stmt = stmt.where(PackingMaterialInventory.purchase_order_id == po.id)
    if material is not None:
        stmt = stmt.where(PackingMaterialInventory.material_name.ilike(f"%{material.split()[0]}%"))
    shortage_only = "short" in normalized or "shortage" in normalized
    if shortage_only:
        stmt = stmt.where(PackingMaterialInventory.shortage_qty > 0)
    rows = list((await db.execute(stmt.limit(12))).scalars().all())
    if not rows:
        if shortage_only:
            count_stmt = select(func.count(PackingMaterialInventory.id))
            if po is not None:
                count_stmt = count_stmt.where(PackingMaterialInventory.purchase_order_id == po.id)
            if material is not None:
                count_stmt = count_stmt.where(PackingMaterialInventory.material_name.ilike(f"%{material.split()[0]}%"))
            total_rows = int((await db.execute(count_stmt)).scalar() or 0)
            if total_rows:
                return "No open packing material shortage found. Packing material rows are available on the Packing Materials page."
        return "No packing material rows found. Use the Packing Materials page and click Generate June materials."
    total_short = sum(Decimal(row.shortage_qty or 0) for row in rows)
    lines = [f"Packing materials: {len(rows)} row(s) found. Total shortage shown: {total_short:f}."]
    for row in rows[:8]:
        lines.append(
            f"- {row.po_number or 'Manual'} | {row.material_name} | required {row.required_qty:f} {row.unit}, "
            f"in stock {row.in_stock_qty:f}, ordered {row.ordered_qty:f}, short {row.shortage_qty:f}."
        )
    if len(rows) > 8:
        lines.append(f"...and {len(rows) - 8} more.")
    return "\n".join(lines)


def _coerce_update_value(value: str, value_type: str) -> Decimal | int | str:
    if value_type == "decimal":
        return Decimal(value)
    if value_type == "int":
        return int(Decimal(value))
    return value


def _display_update_value(value: Decimal | int | str, spec: dict[str, Any]) -> str:
    if spec["type"] == "decimal":
        label = str(spec.get("label", "value")).lower()
        prefix = "Rs " if "price" in label or "mrp" in label or "rate" in label else ""
        return f"{prefix}{Decimal(value):f}"
    return str(value)


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


async def _load_po_by_number(db: AsyncSession, po_number: str) -> PurchaseOrder | None:
    result = await db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_number == po_number)
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
        )
    )
    return result.scalar_one_or_none()


async def _execute_fabric_ordered(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    meters = Decimal(pending.payload["meters"])
    mill_name = str(pending.payload["mill_name"])
    today = date.today()
    product = po.product or (await db.get(Product, po.product_id) if po.product_id else None)
    order = FabricMillOrder(
        purchase_order_id=po.id,
        mill_name=mill_name,
        invoice_number=None,
        ordered_meters=meters,
        ordered_width=getattr(product, "width", None),
        ordered_gsm=getattr(product, "gsm", None),
        ordered_rate_per_meter=None,
        expected_quality_notes="Created from confirmed voice command.",
        committed_delivery_date=today + timedelta(days=7),
        actual_delivery_date=None,
        status=FabricMillOrderStatus.ordered,
        remarks="Voice update: fabric ordered today.",
    )
    db.add(order)

    line = await _line_for_po(db, po)
    if line is not None:
        line.stock_status = "short"
        line.notes = _append_note(line.notes, f"Voice update {today.isoformat()}: ordered {meters} m from {mill_name}.")
    if po.status in {POStatus.draft, POStatus.fabric_check_pending, POStatus.fabric_ready, POStatus.shortage} or _shortage_m(po) > 0:
        po.status = POStatus.shortage
    await _mark_mill_requirement_ordered(db, po)
    db.add(
        Reminder(
            purchase_order_id=po.id,
            reminder_type=ReminderType.mill_delivery_due,
            title="Mill delivery follow-up",
            message=f"Follow up {mill_name} for {meters} m ordered for {po.po_number}.",
            due_date=today + timedelta(days=7),
            assigned_to=None,
            priority=ReminderPriority.high,
            status=ReminderStatus.open,
        )
    )
    await log_audit_event(
        db,
        action_type="voice_fabric_ordered",
        purchase_order_id=po.id,
        entity_type="fabric_mill_order",
        entity_id=str(order.id),
        new_value_json={"po_number": po.po_number, "mill_name": mill_name, "ordered_meters": str(meters)},
        remarks="Confirmed voice command.",
    )
    await db.commit()
    return f"Updated {po.po_number}. Fabric order of {meters} meters from {mill_name} is recorded, and a mill delivery reminder is due in 7 days."


async def _execute_fabric_received(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    meters = Decimal(pending.payload["meters"])
    mill_name = str(pending.payload["mill_name"])
    today = date.today()
    product = po.product
    if product is None:
        product = await db.get(Product, po.product_id) if po.product_id else None
    receipt = FabricReceipt(
        purchase_order_id=po.id,
        supplier_name=mill_name,
        fabric_type=getattr(product, "fabric_type", "Fabric"),
        color=getattr(product, "color", "Assorted"),
        gsm=getattr(product, "gsm", Decimal("0")),
        width=getattr(product, "width", Decimal("0")),
        received_length_m=meters,
        approximate_rolls=None,
        status=ReceiptStatus.approved,
        quality_notes="Created from confirmed voice command.",
        received_width=getattr(product, "width", None),
        received_gsm=getattr(product, "gsm", None),
        received_meters=meters,
        verified_by=None,
        verification_date=today,
        verification_status=FabricVerificationStatus.approved,
        remarks="Voice update: fabric received today.",
        received_at=today,
    )
    db.add(receipt)

    line = await _line_for_po(db, po)
    if line is not None:
        line.stock_meters = (Decimal(line.stock_meters or 0) + meters).quantize(Decimal("0.001"))
        if Decimal(line.stock_meters or 0) > 0:
            line.stock_status = "ok"
        line.notes = _append_note(line.notes, f"Voice update {today.isoformat()}: received {meters} m from {mill_name}.")

    order = await _latest_open_mill_order(db, po)
    if order is not None:
        order.actual_delivery_date = today
        order.status = FabricMillOrderStatus.received if meters >= Decimal(order.ordered_meters or 0) else FabricMillOrderStatus.partially_received

    await ensure_po_operational_data(db, po, commit=False)
    await log_audit_event(
        db,
        action_type="voice_fabric_received",
        purchase_order_id=po.id,
        entity_type="fabric_receipt",
        entity_id=str(receipt.id),
        new_value_json={"po_number": po.po_number, "mill_name": mill_name, "received_meters": str(meters)},
        remarks="Confirmed voice command.",
    )
    await db.commit()
    return f"Updated {po.po_number}. Fabric receipt of {meters} meters from {mill_name} is recorded and the fabric plan has been refreshed."


async def _execute_stage_update(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    stage = StageName(str(pending.payload["stage"]))
    status_by_stage = {
        StageName.fabric_ready: POStatus.fabric_ready,
        StageName.cutting: POStatus.cutting,
        StageName.stitching: POStatus.stitching,
        StageName.size_inspection: POStatus.size_inspection,
        StageName.quality_check: POStatus.quality_check,
        StageName.packing: POStatus.packing,
        StageName.dispatch: POStatus.dispatch,
    }
    old_status = po.status.value
    po.status = status_by_stage[stage]
    await _set_stage_position(db, po, stage)
    line = await _line_for_po(db, po)
    if line is not None:
        if stage == StageName.cutting:
            line.cutting, line.stitching, line.packing, line.dispatch = "in_progress", "pending", "pending", "pending"
        elif stage == StageName.stitching:
            line.cutting, line.stitching, line.packing, line.dispatch = "done", "in_progress", "pending", "pending"
        elif stage in {StageName.size_inspection, StageName.quality_check, StageName.packing}:
            line.cutting, line.stitching, line.packing, line.dispatch = "done", "done", "in_progress", "pending"
        elif stage == StageName.dispatch:
            line.cutting, line.stitching, line.packing, line.dispatch = "done", "done", "done", "pending"
        line.notes = _append_note(line.notes, f"Voice update {date.today().isoformat()}: moved to {stage.value}.")
    await log_audit_event(
        db,
        action_type="voice_stage_update",
        purchase_order_id=po.id,
        entity_type="purchase_order",
        entity_id=str(po.id),
        old_value_json={"status": old_status},
        new_value_json={"status": po.status.value, "stage": stage.value},
        remarks="Confirmed voice command.",
    )
    await db.commit()
    return f"Updated {po.po_number}. It is now shown in {stage.value.replace('_', ' ')} stage."


async def _execute_dispatch_pieces(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    pieces = int(pending.payload["pieces"])
    if pieces <= 0:
        return "Dispatch quantity must be greater than zero, so nothing was updated."
    packing_stage = await _stage_summary(db, po, StageName.packing)
    packed_ready = int(packing_stage.approved_qty if packing_stage is not None else 0)
    summary = await get_dispatch_summary(db, po.id)
    available_to_ship = max(packed_ready - summary.total_dispatched, 0)
    if pieces > available_to_ship:
        return (
            f"I did not dispatch {po.po_number}. Only {available_to_ship} packed pieces are available, "
            f"but you asked to dispatch {pieces}. Update packing first, then dispatch."
        )
    today = date.today()
    payload = DispatchLoadCreate(
        purchase_order_id=po.id,
        load_number=f"VOICE-{po.po_number}-{today.isoformat()}",
        shipped_qty=pieces,
        vehicle_type=None,
        cost_type=DispatchCostType.manual,
        manual_cost=Decimal("0"),
        shipped_at=today,
        document_status="complete",
        remarks="Created from confirmed voice command.",
    )
    try:
        await create_dispatch_load(db, payload)
    except DomainError as error:
        return f"I could not record dispatch for {po.po_number}: {error.detail}"

    refreshed_summary = await get_dispatch_summary(db, po.id)
    line = await _line_for_po(db, po)
    if line is not None:
        line.dispatch = "done" if refreshed_summary.pending_dispatch == 0 else "in_progress"
        line.notes = _append_note(line.notes, f"Voice update {today.isoformat()}: dispatched {pieces} pcs.")
        await db.commit()
    return (
        f"Updated {po.po_number}. Dispatched {pieces} pieces today. "
        f"Remaining pieces are {refreshed_summary.pending_dispatch}."
    )


async def _execute_mark_completed(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    old_status = po.status.value
    summary = await get_dispatch_summary(db, po.id)
    pending_qty = int(summary.pending_dispatch)
    warning = pending.payload.get("warning")
    po.status = POStatus.completed if pending_qty == 0 else POStatus.dispatched_with_exception
    po.actual_delivery_date = date.today()
    await log_audit_event(
        db,
        action_type="voice_mark_po_completed",
        purchase_order_id=po.id,
        entity_type="purchase_order",
        entity_id=str(po.id),
        old_value_json={"status": old_status, "actual_delivery_date": _json_safe_value(po.actual_delivery_date)},
        new_value_json={"status": po.status.value, "pending_dispatch": pending_qty, "warning": warning},
        remarks="Confirmed voice command.",
    )
    await db.commit()
    if pending_qty > 0:
        return f"Updated {po.po_number}. It is marked dispatched with exception because {pending_qty} pieces are still pending."
    return f"Done. {po.po_number} is marked completed."


async def _execute_complete_stage(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    stage = StageName(str(pending.payload["stage"]))
    pieces = int(pending.payload["pieces"])
    if pieces <= 0:
        return "Quantity must be greater than zero, so nothing was updated."
    stage_summary = await _stage_summary(db, po, stage)
    if stage_summary is None:
        await ensure_po_operational_data(db, po, commit=False)
        stage_summary = await _stage_summary(db, po, stage)
    if stage_summary is None:
        return f"I could not find the {stage.value.replace('_', ' ')} stage for {po.po_number}."
    if stage_summary.input_qty <= 0:
        stage_summary.input_qty = int(po.order_quantity_pcs)
        stage_summary.pending_qty = int(po.order_quantity_pcs)
        stage_summary.status = StageStatus.in_progress
        await db.flush()
    available = max(int(stage_summary.pending_qty), 0)
    if pieces > available:
        return f"I could not update {po.po_number}. Only {available} pieces are pending in {stage.value.replace('_', ' ')}."
    try:
        await record_stage_progress(
            db,
            StageProgressCreate(
                purchase_order_id=po.id,
                stage=stage,
                entry_date=date.today(),
                completed_today=pieces,
                approved_today=pieces,
                rejected_today=0,
                repair_today=0,
                alter_today=0,
                moved_to_next_stage_today=pieces,
                remarks="Created from confirmed voice command.",
            ),
            actor_id=None,
            actor_role=None,
        )
    except DomainError as error:
        await db.rollback()
        return f"I could not update {po.po_number}: {error.detail}"
    return f"Done. {stage.value.replace('_', ' ').title()} for {po.po_number} is marked complete for {pieces} pieces."


async def _execute_assign_to_stitching(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    pieces = int(pending.payload["pieces"])
    contractor_name = str(pending.payload["contractor_name"]).strip()
    if pieces <= 0:
        return "Quantity must be greater than zero, so nothing was updated."
    result = await db.execute(
        select(Contractor)
        .where(
            Contractor.is_active.is_(True),
            Contractor.contractor_type == ContractorType.stitching,
            Contractor.name.ilike(f"%{contractor_name}%"),
        )
        .order_by(Contractor.name.asc())
    )
    contractor = result.scalars().first()
    if contractor is None:
        return f"I could not find an active stitching contractor matching {contractor_name}."
    stitching = await _stage_summary(db, po, StageName.stitching)
    if stitching is None:
        await ensure_po_operational_data(db, po, commit=False)
        stitching = await _stage_summary(db, po, StageName.stitching)
    if stitching is None:
        return f"I could not find stitching stage for {po.po_number}."
    if stitching.input_qty <= 0:
        cutting = await _stage_summary(db, po, StageName.cutting)
        available_cut = int(cutting.moved_to_next_qty if cutting else 0)
        if available_cut < pieces:
            return f"I could not assign stitching. Only {available_cut} cut pieces are ready for {po.po_number}."
        stitching.input_qty = available_cut
        stitching.pending_qty = available_cut
        stitching.status = StageStatus.in_progress
        await db.flush()
    try:
        await allocate_contractor(
            db,
            ContractorAllocationCreate(
                stage_summary_id=stitching.id,
                contractor_id=contractor.id,
                issued_qty=pieces,
                expected_completion_date=None,
                notes="Created from confirmed voice command.",
            ),
            actor_id=None,
            actor_role=None,
        )
    except DomainError as error:
        await db.rollback()
        return f"I could not assign stitching for {po.po_number}: {error.detail}"
    return f"Done. {pieces} pieces of {po.po_number} are assigned to {contractor.name} for stitching."


async def _execute_quality_quantities(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    repair = int(pending.payload.get("repair_pieces") or 0)
    alter = int(pending.payload.get("alteration_pieces") or 0)
    rejected = int(pending.payload.get("rejected_pieces") or 0)
    total = repair + alter + rejected
    if total <= 0:
        return "No repair, alteration, or rejected pieces were found, so nothing was updated."
    stage = await _stage_summary(db, po, StageName.stitching)
    if stage is None:
        await ensure_po_operational_data(db, po, commit=False)
        stage = await _stage_summary(db, po, StageName.stitching)
    if stage is None:
        return f"I could not find stitching stage for {po.po_number}."
    if stage.input_qty <= 0:
        stage.input_qty = int(po.order_quantity_pcs)
        stage.pending_qty = int(po.order_quantity_pcs)
        stage.status = StageStatus.in_progress
        await db.flush()
    if total > int(stage.pending_qty):
        return f"I could not record this. Only {stage.pending_qty} pieces are pending in stitching for {po.po_number}."
    try:
        await record_stage_progress(
            db,
            StageProgressCreate(
                purchase_order_id=po.id,
                stage=StageName.stitching,
                entry_date=date.today(),
                completed_today=total,
                approved_today=0,
                rejected_today=rejected,
                repair_today=repair,
                alter_today=alter,
                moved_to_next_stage_today=0,
                remarks="Created from confirmed voice command.",
            ),
            actor_id=None,
            actor_role=None,
        )
    except DomainError as error:
        await db.rollback()
        return f"I could not record quality quantities for {po.po_number}: {error.detail}"
    parts = []
    if repair:
        parts.append(f"{repair} repair")
    if alter:
        parts.append(f"{alter} alteration")
    if rejected:
        parts.append(f"{rejected} rejected")
    return f"Done. {po.po_number} now has {', '.join(parts)} pieces recorded."


async def _execute_update_delivery_date(db: AsyncSession, po: PurchaseOrder, pending: PendingVoiceWrite) -> str:
    new_date = date.fromisoformat(str(pending.payload["date"]))
    old_date = po.promise_delivery_date
    po.promise_delivery_date = new_date
    await log_audit_event(
        db,
        action_type="voice_update_delivery_date",
        purchase_order_id=po.id,
        entity_type="purchase_order",
        entity_id=str(po.id),
        old_value_json={"promise_delivery_date": _json_safe_value(old_date)},
        new_value_json={"promise_delivery_date": new_date.isoformat()},
        remarks="Confirmed voice command.",
    )
    await db.commit()
    return f"Done. Shipment date for {po.po_number} is now {new_date.isoformat()}."


async def _line_for_po(db: AsyncSession, po: PurchaseOrder) -> ProductFabricLine | None:
    result = await db.execute(select(ProductFabricLine).where(ProductFabricLine.product_id == po.product_id))
    return result.scalars().first()


async def _stage_summary(db: AsyncSession, po: PurchaseOrder, stage: StageName) -> StageSummary | None:
    result = await db.execute(
        select(StageSummary).where(
            StageSummary.purchase_order_id == po.id,
            StageSummary.stage == stage,
        )
    )
    return result.scalar_one_or_none()


async def _latest_open_mill_order(db: AsyncSession, po: PurchaseOrder) -> FabricMillOrder | None:
    result = await db.execute(
        select(FabricMillOrder)
        .where(
            FabricMillOrder.purchase_order_id == po.id,
            FabricMillOrder.status.notin_([FabricMillOrderStatus.received, FabricMillOrderStatus.cancelled]),
        )
        .order_by(FabricMillOrder.created_at.desc())
    )
    return result.scalars().first()


async def _mark_mill_requirement_ordered(db: AsyncSession, po: PurchaseOrder) -> None:
    result = await db.execute(
        select(MillOrderRequirement)
        .where(MillOrderRequirement.purchase_order_id == po.id)
        .order_by(MillOrderRequirement.created_at.desc())
    )
    requirement = result.scalars().first()
    if requirement is not None:
        requirement.status = MillOrderRequirementStatus.mill_order_created


async def _set_stage_position(db: AsyncSession, po: PurchaseOrder, active_stage: StageName) -> None:
    result = await db.execute(select(StageSummary).where(StageSummary.purchase_order_id == po.id))
    existing = {row.stage: row for row in result.scalars().all()}
    stages = (
        StageName.fabric_ready,
        StageName.cutting,
        StageName.stitching,
        StageName.size_inspection,
        StageName.quality_check,
        StageName.packing,
        StageName.dispatch,
    )
    active_index = stages.index(active_stage)
    qty = int(po.order_quantity_pcs)
    for index, stage in enumerate(stages):
        row = existing.get(stage)
        if row is None:
            row = StageSummary(purchase_order_id=po.id, stage=stage, sequence=index)
            db.add(row)
        row.sequence = index
        if index < active_index:
            row.input_qty = qty
            row.completed_qty = qty
            row.approved_qty = qty
            row.moved_to_next_qty = qty
            row.pending_qty = 0
            row.status = StageStatus.completed
        elif index == active_index:
            row.input_qty = qty
            row.completed_qty = 0
            row.approved_qty = 0
            row.moved_to_next_qty = 0
            row.pending_qty = qty
            row.status = StageStatus.in_progress
        else:
            row.input_qty = 0
            row.completed_qty = 0
            row.approved_qty = 0
            row.moved_to_next_qty = 0
            row.pending_qty = 0
            row.status = StageStatus.not_started


def _extract_meters(normalized: str) -> Decimal | None:
    patterns = [
        r"(\d[\d,]*(?:\.\d+)?)\s*(?:m|meter|meters)\b",
        r"(?:length|fabric)\s+(?:is\s+)?(?:of\s+)?(\d[\d,]*(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return Decimal(match.group(1).replace(",", ""))
    return None


def _mentions_packing_material(normalized: str) -> bool:
    phrase_tokens = ("packing material", "packing materials", "insert card")
    word_tokens = ("polybag", "packet", "tag", "header", "label", "insert", "stiffener", "bag", "carton", "bale", "tape")
    return any(token in normalized for token in phrase_tokens) or any(
        re.search(rf"\b{re.escape(token)}\b", normalized) for token in word_tokens
    )


def _packing_material_field(normalized: str) -> str | None:
    if "printed consumption" in normalized or "printed consumed" in normalized:
        return "printed_consumption_qty"
    if "actual consumption" in normalized or "actual consumed" in normalized:
        return "actual_consumption_qty"
    if "printed stock" in normalized:
        return "printed_stock_qty"
    if "actual stock" in normalized or "physical stock" in normalized:
        return "actual_stock_qty"
    if any(token in normalized for token in ("in stock", "stock", "available")):
        return "actual_stock_qty"
    if any(token in normalized for token in ("ordered", "orderd", "order placed")):
        return "ordered_qty"
    if any(token in normalized for token in ("received", "recieved")):
        return "received_qty"
    if any(token in normalized for token in ("consumed", "used")):
        return "actual_consumption_qty"
    if any(token in normalized for token in ("required", "needed", "need")):
        return "required_qty"
    if "supplier" in normalized:
        return "supplier_name"
    return None


def _packing_material_name(normalized: str) -> str | None:
    if "tag" in normalized:
        return "Tag"
    if "header" in normalized:
        return "Header"
    if "stiffener" in normalized:
        return "Stiffener"
    if "bag" in normalized:
        return "Bag"
    if "polybag" in normalized or "packet" in normalized:
        return "Polybag / packet"
    if "brand label" in normalized or "label" in normalized:
        return "Brand label"
    if "insert" in normalized or "card" in normalized:
        return "Insert"
    if "carton" in normalized or "bale" in normalized:
        return "Master bale / carton"
    if "tape" in normalized:
        return "Tape roll"
    return None


def _extract_packing_material_value(raw_text: str, normalized: str, field: str) -> Decimal | str | None:
    if field == "supplier_name":
        match = re.search(r"(?:supplier|from|by)\s+([A-Za-z0-9 &.-]+)$", raw_text, re.IGNORECASE)
        return re.sub(r"\s+", " ", match.group(1).strip()) if match else None
    patterns = [
        r"(?:to|with|as|at)\s*(\d[\d,]*(?:\.\d+)?)",
        r"(?:stock|ordered|orderd|received|recieved|consumed|used|required|needed)\s*(?:is|to|with|as|at)?\s*(\d[\d,]*(?:\.\d+)?)",
        r"(\d[\d,]*(?:\.\d+)?)\s*(?:pcs|pieces|piece|rolls?|bales?|cartons?|qty|quantity)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return Decimal(match.group(1).replace(",", ""))
    return None


async def _matching_packing_material_rows(
    db: AsyncSession,
    po_numbers: list[str],
    material: str,
) -> list[PackingMaterialInventory]:
    stmt = select(PackingMaterialInventory).where(PackingMaterialInventory.material_name == material)
    if po_numbers:
        stmt = stmt.where(PackingMaterialInventory.po_number.in_(po_numbers))
    result = await db.execute(stmt.order_by(PackingMaterialInventory.po_number.asc()))
    return list(result.scalars().all())


def _po_status_from_text(normalized: str) -> POStatus | None:
    status_aliases = {
        POStatus.fabric_ready: ("fabric ready", "fabric_ready", "ready fabric"),
        POStatus.shortage: ("shortage", "fabric shortage", "short"),
        POStatus.cutting: ("cutting",),
        POStatus.stitching: ("stitching",),
        POStatus.packing: ("packing",),
        POStatus.dispatch: ("dispatch", "ready for dispatch"),
        POStatus.partially_dispatched: ("partially dispatched", "partial dispatch"),
        POStatus.dispatched_with_exception: ("dispatch exception", "dispatched with exception"),
        POStatus.completed: ("completed", "complete", "done"),
        POStatus.delayed: ("delayed", "late"),
        POStatus.cancelled: ("cancelled", "canceled"),
        POStatus.draft: ("draft",),
    }
    for status, aliases in status_aliases.items():
        if any(alias in normalized for alias in aliases):
            return status
    return None


def _stage_for_po_status(status: POStatus) -> StageName | None:
    return {
        POStatus.fabric_ready: StageName.fabric_ready,
        POStatus.cutting: StageName.cutting,
        POStatus.stitching: StageName.stitching,
        POStatus.size_inspection: StageName.size_inspection,
        POStatus.quality_check: StageName.quality_check,
        POStatus.packing: StageName.packing,
        POStatus.dispatch: StageName.dispatch,
        POStatus.partially_dispatched: StageName.dispatch,
        POStatus.dispatched_with_exception: StageName.dispatch,
        POStatus.completed: StageName.dispatch,
    }.get(status)


def _extract_pieces(normalized: str) -> int | None:
    patterns = [
        r"(\d[\d,]*)\s*(?:pcs|pieces|piece)\b",
        r"(?:dispatch(?:ed)?|shipped|ship)\s+(\d[\d,]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return int(Decimal(match.group(1).replace(",", "")))
    return None


def _extract_mill_name(raw_text: str) -> str | None:
    match = re.search(r"(?:from|by|with)\s+([A-Za-z0-9 &.-]+?\s+Mill)\b", raw_text, re.IGNORECASE)
    if match:
        return re.sub(r"\s+", " ", match.group(1).strip())
    return None


def _append_note(existing: str | None, note: str) -> str:
    return f"{existing}\n{note}" if existing else note


def _is_confirm(normalized: str) -> bool:
    return normalized in {"yes", "confirm", "go ahead", "do it", "haan", "ok", "okay", "yes update", "update it"}


def _is_cancel(normalized: str) -> bool:
    return normalized in {"no", "cancel", "stop", "do not", "don't", "dont", "cancel it"}


async def _maybe_generate_pdf(db: AsyncSession, normalized: str, pos: list[PurchaseOrder]) -> str | None:
    if "pdf" not in normalized and "report" not in normalized:
        return None
    report_type = None
    filters = {}
    if "quotation" in normalized or "quote" in normalized:
        return None
    if "fabric shortage" in normalized or "shortage" in normalized:
        report_type = "generate_pdf_fabric_shortage"
    elif "pending dispatch" in normalized:
        report_type = "generate_pdf_pending_dispatch"
    elif "running po" in normalized or "running pos" in normalized or "active po" in normalized:
        report_type = "generate_pdf_running_pos"
    elif "june" in normalized and "dispatch" in normalized:
        report_type = "generate_pdf_june_dispatch"
        filters = {"month": 6, "year": _current_year_for_june(pos)}
    elif "delayed" in normalized:
        report_type = "generate_pdf_delayed_pos"
    if report_type is None:
        return None
    if report_type not in REPORT_REGISTRY:
        return f"That PDF type is not registered yet: {report_type}."
    service = ReportService(db)
    request = await service.create_request(ReportGenerateRequest(report_type=report_type, filters=filters), requested_by=None)
    generated = await service.generate_report(request.id)
    if generated.status.value != "completed" or not generated.download_url:
        return f"PDF generation failed: {generated.error_message or 'unknown error'}."
    add_artifact(
        {
            "type": "pdf",
            "title": generated.title,
            "report_type": report_type,
            "report_id": str(generated.id),
            "download_url": generated.download_url,
        }
    )
    return f"{generated.title} is ready."


async def _maybe_answer_quotation(db: AsyncSession, normalized: str, raw_text: str, pos: list[PurchaseOrder]) -> str | None:
    if "quotation" not in normalized and "quote" not in normalized:
        return None
    po = _extract_po(pos, raw_text)
    if po is None:
        return "Please tell me the PO number for the quotation."
    if "pdf" in normalized or "download" in normalized or "generate" in normalized or "create" in normalized:
        quotation, _ = await generate_po_quotation_pdf(db, po.po_number)
        add_artifact(
            {
                "type": "pdf",
                "title": f"Quotation - {quotation.po_number}",
                "report_type": "quotation",
                "report_id": quotation.po_number,
                "download_url": f"/api/v1/quotations/{quote(quotation.po_number, safe='')}/pdf",
            }
        )
        missing = f" Missing fields: {', '.join(quotation.missing_fields)}." if quotation.missing_fields else ""
        return f"Quotation PDF is ready for {quotation.po_number}.{missing}"
    quotation = await build_po_quotation(db, po.po_number)
    total = f"Rs {quotation.total_amount}" if quotation.total_amount is not None else "total not available"
    missing = f" Missing fields: {', '.join(quotation.missing_fields)}." if quotation.missing_fields else ""
    return (
        f"Quotation for {quotation.po_number}: {quotation.quantity_pcs} pcs, "
        f"unit price {quotation.unit_price if quotation.unit_price is not None else 'not recorded'}, {total}. "
        f"Dispatch date {quotation.dispatch_date.isoformat()}.{missing}"
    )


async def _answer_specific_po(db: AsyncSession, po: PurchaseOrder, normalized: str) -> str:
    allocations = await _allocations(db, po)
    summary = _po_line(po)
    if "contractor" in normalized:
        if not allocations:
            return f"No contractor allocation is recorded for {po.po_number}."
        lines = [
            f"{item.stage.value}: {item.contractor.name if item.contractor else 'Contractor'} "
            f"issued {item.issued_qty}, pending {max(item.issued_qty - item.completed_qty, 0)}"
            for item in allocations
        ]
        return "\n".join(lines)
    if "expected completion" in normalized or "completion date" in normalized:
        if po.status == POStatus.completed and po.actual_delivery_date:
            return f"{po.po_number} is completed. Actual delivery date: {po.actual_delivery_date.isoformat()}."
        return f"{po.po_number} promised dispatch date is {po.promise_delivery_date.isoformat()}. Current status: {po.status.value}."
    if "ready for dispatch" in normalized:
        ready = _dispatch_ready_qty(po)
        return f"{po.po_number} ready for dispatch qty: {ready}. Status: {po.status.value}."
    if "why" in normalized and "delayed" in normalized:
        return _delay_reason(po)
    if any(key in normalized for key in ("cutting", "stitching", "finishing", "quality", "stage")):
        wanted = _stage_from_text(normalized)
        stages = [stage for stage in po.stage_summaries if wanted is None or stage.stage == wanted]
        if not stages:
            return f"No stage data is recorded for {po.po_number}."
        return "\n".join(f"{po.po_number} {_stage_label(stage.stage)}: {_stage_line(stage)}" for stage in stages)
    if "pending" in normalized or "completed" in normalized or "rejected" in normalized or "approved" in normalized:
        return _quantity_breakdown(po)
    if "shortage" in normalized:
        return _shortage_line(po)
    return summary + "\n" + _quantity_breakdown(po)


def _answer_june_query(pos: list[PurchaseOrder], normalized: str) -> str:
    june = [po for po in pos if po.promise_delivery_date.month == 6 or po.order_date.month == 6]
    if not june:
        return "No June POs are present in the database."
    if "dispatch status" in normalized:
        return _june_dispatch_status(june)
    if "pending" in normalized:
        pending = [po for po in june if _pending_qty(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
        return _format_po_list("June pending POs", pending)
    if "completed" in normalized:
        completed = [po for po in june if po.status == POStatus.completed]
        return _format_po_list("June completed POs", completed)
    if "delayed" in normalized:
        return _format_po_list("June delayed POs", _delayed(june))
    if "shortage" in normalized or "risky" in normalized or "risk" in normalized:
        risky = [po for po in june if _shortage_m(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
        return _format_po_list("June shortage/risk POs", risky)
    if "end of june" in normalized or "june end" in normalized or "before june 30" in normalized or "by june 30" in normalized:
        due = [po for po in june if po.promise_delivery_date <= date(po.promise_delivery_date.year, 6, 30)]
        return _format_po_list("June POs due by June 30", due)
    return _format_po_list("All June POs", june, include_pending=False)


def _june_dispatch_status(june: list[PurchaseOrder]) -> str:
    completed = [po for po in june if po.status == POStatus.completed]
    pending = [po for po in june if _pending_qty(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
    shortage = [po for po in pending if _shortage_m(po) > 0]
    ready = [po for po in pending if _dispatch_ready_qty(po) > 0]
    return (
        f"June dispatch status: {len(june)} POs, {len(completed)} completed, "
        f"{len(pending)} pending, {len(shortage)} with fabric shortage, {len(ready)} ready for dispatch.\n"
        + _format_po_list("Pending June POs", pending, limit=8)
    )


def _factory_summary(pos: list[PurchaseOrder]) -> str:
    active = [po for po in pos if po.status not in TERMINAL_PO_STATUSES]
    shortages = [po for po in active if _shortage_m(po) > 0]
    delayed = _delayed(active)
    ready = [po for po in active if _dispatch_ready_qty(po) > 0]
    return (
        f"Factory summary: {len(pos)} total POs, {len(active)} active, {len(delayed)} delayed, "
        f"{len(shortages)} fabric shortages, {len(ready)} ready for dispatch."
    )


def _biggest_risk(pos: list[PurchaseOrder]) -> str:
    active = [po for po in pos if po.status not in TERMINAL_PO_STATUSES]
    shortages = sorted([po for po in active if _shortage_m(po) > 0], key=_shortage_m, reverse=True)
    if shortages:
        top = shortages[0]
        return f"Biggest risk: fabric shortage on {top.po_number}, short by {round(_shortage_m(top), 3)} m. Focus there first."
    delayed = _delayed(active)
    if delayed:
        return f"Biggest risk: {len(delayed)} delayed POs. First: {delayed[0].po_number}."
    pending = sorted(active, key=lambda po: po.promise_delivery_date)
    if pending:
        return f"Focus today on {pending[0].po_number}: status {pending[0].status.value}, deadline {pending[0].promise_delivery_date.isoformat()}."
    return "No active PO risk is visible from the current database."


def _list_shortages(pos: list[PurchaseOrder]) -> str:
    rows = [po for po in pos if _shortage_m(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
    return _format_po_list("POs with fabric shortage", rows)


def _list_mill_requirements(pos: list[PurchaseOrder]) -> str:
    rows = [po for po in pos if _shortage_m(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
    if not rows:
        return "No mill purchase requirement is visible from current fabric plans."
    lines = [f"Mill purchase requirements: {len(rows)} POs need fabric."]
    for po in rows[:12]:
        fabric_name = po.design_code_snapshot or (po.product.product_name if po.product else "fabric")
        lines.append(f"- {po.po_number}: order about {round(_shortage_m(po), 3)} m for {fabric_name}.")
    if len(rows) > 12:
        lines.append(f"...and {len(rows) - 12} more.")
    return "\n".join(lines)


async def _list_mill_invoices(db: AsyncSession) -> str:
    result = await db.execute(
        select(FabricMillOrder)
        .order_by(FabricMillOrder.created_at.asc())
    )
    orders = list(result.scalars().all())
    if not orders:
        return "No mill invoices or fabric mill orders are recorded right now."
    lines = [f"Mill invoices/orders: {len(orders)} recorded."]
    for order in orders[:15]:
        po = await db.get(PurchaseOrder, order.purchase_order_id)
        po_number = po.po_number if po else "PO"
        rate = f" at {order.ordered_rate_per_meter}/m" if order.ordered_rate_per_meter is not None else ""
        lines.append(
            f"- {po_number}: {order.mill_name}, {round(float(order.ordered_meters or 0), 3)} m{rate}, "
            f"due {order.committed_delivery_date.isoformat()}, status {order.status.value}."
        )
    if len(orders) > 15:
        lines.append(f"...and {len(orders) - 15} more.")
    return "\n".join(lines)


def _po_mill_requirement(po: PurchaseOrder) -> str:
    shortage = _shortage_m(po)
    if shortage <= 0 or po.status in TERMINAL_PO_STATUSES:
        return f"No open mill purchase requirement is visible for {po.po_number}."
    fabric_name = po.design_code_snapshot or (po.product.product_name if po.product else "fabric")
    return f"{po.po_number}: order about {round(shortage, 3)} m for {fabric_name}."


def _list_dispatch_ready(pos: list[PurchaseOrder]) -> str:
    rows = [po for po in pos if _dispatch_ready_qty(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
    return _format_po_list("Ready-to-dispatch POs", rows)


def _list_ordered_not_received(pos: list[PurchaseOrder]) -> str:
    rows = [
        po for po in pos
        if po.status not in TERMINAL_PO_STATUSES
        and (
            "orderd but not received" in (po.notes or "").lower()
            or "ordered but not received" in (po.notes or "").lower()
            or (po.fabric_plan is not None and float(po.fabric_plan.shortage_m or 0) > 0)
        )
    ]
    return _format_po_list("Fabric ordered but not received / still short", rows)


def _list_fabric_ready(pos: list[PurchaseOrder]) -> str:
    rows = [
        po for po in pos
        if po.status not in TERMINAL_PO_STATUSES
        and po.fabric_plan is not None
        and float(po.fabric_plan.shortage_m or 0) <= 0
        and po.status in {POStatus.fabric_ready, POStatus.cutting, POStatus.stitching, POStatus.packing, POStatus.dispatch, POStatus.partially_dispatched}
    ]
    return _format_po_list("POs with fabric ready", rows)


def _list_due_this_week(pos: list[PurchaseOrder]) -> str:
    today = date.today()
    end = today + timedelta(days=7)
    rows = [
        po for po in pos
        if po.status not in TERMINAL_PO_STATUSES
        and today <= po.promise_delivery_date <= end
    ]
    if not rows:
        return f"No active POs are due between {today.isoformat()} and {end.isoformat()}."
    return _format_po_list(f"POs due between {today.isoformat()} and {end.isoformat()}", rows)


def _answer_king_fabric_requirement(pos: list[PurchaseOrder]) -> str:
    rows = [po for po in pos if "king" in ((po.product.product_name if po.product else "") + " " + (po.notes or "")).lower()]
    if not rows:
        rows = [po for po in pos if po.product and po.product.product_name.startswith("499")]
    if not rows:
        return "No king-size PO is visible in the current database."
    lines = [f"King-size fabric requirement: {len(rows)} matching POs."]
    for po in rows[:10]:
        plan = po.fabric_plan
        total_required = float(po.order_quantity_pcs or 0)
        if po.product and po.product.per_piece_fabric_usage_m:
            total_required = float(Decimal(po.order_quantity_pcs) * Decimal(po.product.per_piece_fabric_usage_m))
        if plan is None:
            lines.append(f"- {po.po_number}: total PO requirement about {round(total_required, 3)} m; fabric plan is not recorded.")
        else:
            lines.append(
                f"- {po.po_number}: total PO requirement about {round(total_required, 3)} m, "
                f"remaining to make {round(float(plan.total_required_m or 0), 3)} m, "
                f"shortage {round(float(plan.shortage_m or 0), 3)} m."
            )
    if len(rows) > 10:
        lines.append(f"...and {len(rows) - 10} more.")
    return "\n".join(lines)


def _owner_demo_talking_points(pos: list[PurchaseOrder]) -> str:
    total = len(pos)
    ordered_not_received = [po for po in pos if "orderd but not received" in (po.notes or "").lower() or "ordered but not received" in (po.notes or "").lower()]
    fabric_ready = [po for po in pos if po.fabric_plan and float(po.fabric_plan.shortage_m or 0) <= 0]
    dispatch_ready = [po for po in pos if _dispatch_ready_qty(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
    return (
        f"Show the owner these four points: 1. The June sheet is loaded with {total} PO rows only. "
        f"2. {len(ordered_not_received)} POs have fabric ordered but not received, so follow-up is visible. "
        f"3. {len(fabric_ready)} POs have fabric ready or received and can move through production. "
        f"4. {len(dispatch_ready)} POs have dispatch-ready pieces, and truck planning now uses 14, 15, 17, 20, 24 and 26 feet vehicles."
    )


def _list_pending_dispatch(pos: list[PurchaseOrder]) -> str:
    rows = [po for po in pos if _dispatch_pending_qty(po) > 0 and po.status not in TERMINAL_PO_STATUSES]
    return _format_po_list("Pending dispatch POs", rows)


def _list_delayed(pos: list[PurchaseOrder]) -> str:
    return _format_po_list("Delayed POs", _delayed(pos))


def _list_stage_pending(pos: list[PurchaseOrder], stage_name: StageName, label: str) -> str:
    rows = []
    for po in pos:
        if po.status in TERMINAL_PO_STATUSES:
            continue
        stage = next((item for item in po.stage_summaries if item.stage == stage_name), None)
        if stage and stage.pending_qty > 0:
            rows.append(po)
    return _format_po_list(f"POs pending in {label}", rows)


def _format_po_list(title: str, rows: Iterable[PurchaseOrder], *, limit: int = 12, include_pending: bool = True) -> str:
    items = list(rows)
    if not items:
        return f"{title}: none found in the current database."
    lines = [f"{title}: {len(items)} found."]
    for po in items[:limit]:
        line = _po_line(po, include_pending=include_pending)
        lines.append(line)
    if len(items) > limit:
        lines.append(f"...and {len(items) - limit} more.")
    return "\n".join(lines)


def _answer_price_or_rate_query(pos: list[PurchaseOrder], normalized: str) -> str | None:
    """Answer owner questions such as "details of 69 price rate PO" from DB.

    In the June data, phrases like "69 rate PO" usually refer to a rate/category
    prefix in the product name, not only to a numeric selling_price column.
    Keeping this deterministic prevents common demo questions from falling
    through to Gemini when the API key is unavailable or invalid.
    """
    has_price_words = any(word in normalized for word in ("price", "rate", "mrp", "selling"))
    has_po_words = "po" in normalized or "order" in normalized or "details" in normalized
    if not (has_price_words and has_po_words):
        return None

    numbers = [token.replace(",", "") for token in re.findall(r"\d+(?:\.\d+)?", normalized)]
    if not numbers:
        return "Please tell me the price/rate number, for example: show me 69 rate POs."

    matches: list[PurchaseOrder] = []
    for po in pos:
        product_name = (po.product.product_name if po.product else "").lower()
        design_name = (po.design_name_snapshot or "").lower()
        design_code = (po.design_code_snapshot or "").lower()
        values = {
            str(po.selling_price).rstrip("0").rstrip(".") if po.selling_price is not None else "",
            str(po.mrp).rstrip("0").rstrip(".") if po.mrp is not None else "",
        }
        for number in numbers:
            if (
                number in values
                or product_name.startswith(f"{number}-")
                or product_name.startswith(f"{number} ")
                or f" {number}-" in product_name
                or design_name.startswith(f"{number}-")
                or design_code.startswith(f"{number}-")
            ):
                matches.append(po)
                break

    if not matches:
        return f"I could not find any PO matching price/rate {', '.join(numbers)} in the current database."

    title = f"POs matching price/rate {', '.join(numbers)}"
    lines = [f"{title}: {len(matches)} found."]
    for po in matches[:15]:
        product = po.product.product_name if po.product else po.design_name_snapshot or "Product not recorded"
        selling = _format_money(po.selling_price, "selling price")
        mrp = _format_money(po.mrp, "MRP")
        lines.append(
            f"- {po.po_number}: {product}, {po.order_quantity_pcs} pcs, "
            f"{selling}, {mrp}, status {po.status.value}, deadline {po.promise_delivery_date.isoformat()}."
        )
    if len(matches) > 15:
        lines.append(f"...and {len(matches) - 15} more.")
    return "\n".join(lines)


def _format_money(value: Decimal | None, label: str) -> str:
    if value is None:
        return f"{label} not recorded"
    normalized = Decimal(value).normalize()
    return f"{label} Rs {normalized:f}"


def _po_line(po: PurchaseOrder, *, include_pending: bool = True) -> str:
    bits = [
        f"{po.po_number}",
        f"{po.order_quantity_pcs} pcs",
        f"status {po.status.value}",
        f"deadline {po.promise_delivery_date.isoformat()}",
    ]
    if include_pending:
        bits.append(f"pending {_pending_qty(po)}")
    shortage = _shortage_m(po)
    if shortage > 0 and po.status not in TERMINAL_PO_STATUSES:
        bits.append(f"short {round(shortage, 3)} m")
    bottleneck = next((stage for stage in po.stage_summaries if stage.pending_qty > 0 and stage.stage.value != "dispatch"), None)
    if bottleneck and po.status not in TERMINAL_PO_STATUSES:
        bits.append(f"bottleneck {_stage_label(bottleneck.stage)}")
    return "- " + " | ".join(bits)


def _quantity_breakdown(po: PurchaseOrder) -> str:
    totals = {
        "completed": _dispatch_completed(po),
        "pending": _pending_qty(po),
        "rejected": sum(int(stage.rejected_qty or 0) for stage in po.stage_summaries),
        "repair": sum(int(stage.repair_qty or 0) for stage in po.stage_summaries),
        "alter": sum(int(stage.alter_qty or 0) for stage in po.stage_summaries),
        "approved": max([int(stage.approved_qty or 0) for stage in po.stage_summaries] + [0]),
    }
    return (
        f"{po.po_number}: completed {totals['completed']}, pending {totals['pending']}, "
        f"approved {totals['approved']}, rejected {totals['rejected']}, repair {totals['repair']}, altered {totals['alter']}."
    )


def _shortage_line(po: PurchaseOrder) -> str:
    if po.fabric_plan is None:
        return f"No fabric plan is recorded for {po.po_number}."
    return (
        f"{po.po_number} fabric: required {po.fabric_plan.total_required_m} m, "
        f"available {po.fabric_plan.available_m} m, shortage {po.fabric_plan.shortage_m} m."
    )


def _delay_reason(po: PurchaseOrder) -> str:
    if po.promise_delivery_date >= date.today() or _pending_qty(po) == 0:
        return f"{po.po_number} is not delayed from the current database. Deadline is {po.promise_delivery_date.isoformat()}."
    if _shortage_m(po) > 0:
        return f"{po.po_number} is delayed because fabric is short by {round(_shortage_m(po), 3)} m."
    bottleneck = next((stage for stage in po.stage_summaries if stage.pending_qty > 0), None)
    if bottleneck:
        return f"{po.po_number} is delayed because {_stage_label(bottleneck.stage)} still has {bottleneck.pending_qty} pcs pending."
    return f"{po.po_number} is delayed, but no blocker is recorded in stages or fabric plan."


def _stage_line(stage: StageSummary) -> str:
    return (
        f"status {stage.status.value}, input {stage.input_qty}, completed {stage.completed_qty}, "
        f"approved {stage.approved_qty}, rejected {stage.rejected_qty}, repair {stage.repair_qty}, "
        f"altered {stage.alter_qty}, pending {stage.pending_qty}."
    )


def _stage_from_text(normalized: str) -> StageName | None:
    if "cutting" in normalized:
        return StageName.cutting
    if "stitching" in normalized:
        return StageName.stitching
    if "finishing" in normalized or "quality" in normalized:
        return StageName.quality_check
    if "packing" in normalized:
        return StageName.packing
    if "dispatch" in normalized:
        return StageName.dispatch
    return None


def _stage_label(stage: StageName) -> str:
    if stage == StageName.quality_check:
        return "finishing/quality check"
    return stage.value.replace("_", " ")


async def _allocations(db: AsyncSession, po: PurchaseOrder) -> list[ContractorAllocation]:
    result = await db.execute(
        select(ContractorAllocation)
        .join(StageSummary, StageSummary.id == ContractorAllocation.stage_summary_id)
        .where(StageSummary.purchase_order_id == po.id)
        .options(selectinload(ContractorAllocation.contractor))
        .order_by(ContractorAllocation.created_at.desc())
    )
    return list(result.scalars().all())


async def _list_delayed_contractors(db: AsyncSession) -> str:
    result = await db.execute(
        select(ContractorAllocation)
        .join(StageSummary, StageSummary.id == ContractorAllocation.stage_summary_id)
        .options(
            selectinload(ContractorAllocation.contractor),
            selectinload(ContractorAllocation.stage_summary).selectinload(StageSummary.purchase_order),
        )
        .where(
            ContractorAllocation.expected_completion_date.is_not(None),
            ContractorAllocation.expected_completion_date < date.today(),
            ContractorAllocation.completed_qty < ContractorAllocation.issued_qty,
        )
        .order_by(ContractorAllocation.expected_completion_date.asc())
    )
    rows = list(result.scalars().all())
    if not rows:
        return "No delayed contractor allocation is recorded in the current database."
    lines = [f"Delayed contractor allocations: {len(rows)} found."]
    for item in rows[:12]:
        contractor = item.contractor.name if item.contractor else "Contractor"
        po_number = item.stage_summary.purchase_order.po_number if item.stage_summary and item.stage_summary.purchase_order else "PO"
        pending = max(int(item.issued_qty or 0) - int(item.completed_qty or 0), 0)
        lines.append(f"- {contractor}: {po_number} {item.stage.value}, pending {pending}, due {item.expected_completion_date.isoformat()}.")
    if len(rows) > 12:
        lines.append(f"...and {len(rows) - 12} more.")
    return "\n".join(lines)


def _delayed(pos: Iterable[PurchaseOrder]) -> list[PurchaseOrder]:
    today = date.today()
    return [po for po in pos if po.promise_delivery_date < today and _pending_qty(po) > 0 and po.status not in TERMINAL_PO_STATUSES]


def _pending_qty(po: PurchaseOrder) -> int:
    return max(int(po.order_quantity_pcs) - _dispatch_completed(po), 0)


def _dispatch_completed(po: PurchaseOrder) -> int:
    dispatch = next((stage for stage in po.stage_summaries if stage.stage == StageName.dispatch), None)
    stage_qty = int(dispatch.completed_qty or 0) if dispatch else 0
    load_qty = sum(int(load.shipped_qty or 0) for load in po.dispatch_loads)
    if po.status == POStatus.completed:
        return max(int(po.order_quantity_pcs), stage_qty, load_qty)
    return max(stage_qty, load_qty)


def _dispatch_ready_qty(po: PurchaseOrder) -> int:
    packing = next((stage for stage in po.stage_summaries if stage.stage == StageName.packing), None)
    if packing is None:
        return 0
    return max(int(packing.approved_qty or 0) - _dispatch_completed(po), 0)


def _dispatch_pending_qty(po: PurchaseOrder) -> int:
    dispatch = next((stage for stage in po.stage_summaries if stage.stage == StageName.dispatch), None)
    return int(dispatch.pending_qty or 0) if dispatch else 0


def _shortage_m(po: PurchaseOrder) -> float:
    if po.fabric_plan is None:
        return 0.0
    return float(po.fabric_plan.shortage_m or 0)


def _extract_po(pos: list[PurchaseOrder], text: str) -> PurchaseOrder | None:
    lowered = text.lower()
    exact = sorted(pos, key=lambda po: len(po.po_number), reverse=True)
    for po in exact:
        if po.po_number.lower() in lowered:
            return po
    candidates = re.findall(r"[A-Za-z0-9][A-Za-z0-9&#/_-]{2,}", text)
    for token in sorted(candidates, key=len, reverse=True):
        token_l = token.lower()
        matches = [
            po for po in pos
            if token_l in po.po_number.lower()
            or (po.design_code_snapshot and token_l in po.design_code_snapshot.lower())
            or (po.design_name_snapshot and token_l in po.design_name_snapshot.lower())
            or (po.product and token_l in po.product.product_name.lower())
        ]
        if len(matches) == 1:
            return matches[0]
    return None


def _current_year_for_june(pos: list[PurchaseOrder]) -> int:
    years = [po.promise_delivery_date.year for po in pos if po.promise_delivery_date.month == 6]
    return max(set(years), key=years.count) if years else date.today().year


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _is_greeting(normalized: str) -> bool:
    return normalized in {"hi", "hello", "hey", "namaste", "hii"} or normalized.startswith("hello ")
