"""Purchase-order tools for the voice assistant.

IMPORTANT: Do NOT add ``from __future__ import annotations`` here. The
google-genai SDK introspects concrete annotation objects for function calling.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models.enums import POStatus
from app.models.purchase_order import PurchaseOrder
from app.models.stage import ContractorAllocation, StageSummary
from app.services.operational_backfill import ensure_all_operational_data, ensure_po_operational_data

from ..db_context import current_session
from ..tools import tool


_TERMINAL = {POStatus.completed, POStatus.cancelled}


def _to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _stage_payload(stage: StageSummary) -> dict:
    return {
        "stage": stage.stage.value,
        "status": stage.status.value,
        "input_qty": int(stage.input_qty or 0),
        "completed_qty": int(stage.completed_qty or 0),
        "approved_qty": int(stage.approved_qty or 0),
        "rejected_qty": int(stage.rejected_qty or 0),
        "repair_qty": int(stage.repair_qty or 0),
        "alter_qty": int(stage.alter_qty or 0),
        "moved_to_next_qty": int(stage.moved_to_next_qty or 0),
        "pending_qty": int(stage.pending_qty or 0),
    }


def _dispatch_completed(po: PurchaseOrder) -> int:
    stage = next((item for item in po.stage_summaries if item.stage.value == "dispatch"), None)
    stage_qty = int(stage.completed_qty or 0) if stage else 0
    load_qty = sum(int(load.shipped_qty or 0) for load in po.dispatch_loads)
    if po.status == POStatus.completed:
        return max(int(po.order_quantity_pcs), stage_qty, load_qty)
    return max(stage_qty, load_qty)


def _po_summary(po: PurchaseOrder) -> dict:
    completed_qty = _dispatch_completed(po)
    pending_qty = max(int(po.order_quantity_pcs) - completed_qty, 0)
    shortage_m = 0.0
    fabric_status = None
    if po.fabric_plan is not None:
        shortage_m = _to_float(po.fabric_plan.shortage_m)
        fabric_status = po.fabric_plan.status.value
    bottleneck = next((stage for stage in po.stage_summaries if stage.pending_qty > 0 and stage.stage.value != "dispatch"), None)
    return {
        "po_number": po.po_number,
        "product": po.product.product_name if po.product else "Product",
        "design_code": po.design_code_snapshot,
        "design_name": po.design_name_snapshot,
        "quantity_pieces": int(po.order_quantity_pcs),
        "order_date": po.order_date.isoformat(),
        "shipment_date": po.promise_delivery_date.isoformat(),
        "actual_delivery_date": po.actual_delivery_date.isoformat() if po.actual_delivery_date else None,
        "status": po.status.value,
        "completed_qty": completed_qty,
        "pending_qty": pending_qty,
        "fabric_status": fabric_status,
        "shortage_meters": shortage_m,
        "bottleneck_stage": bottleneck.stage.value if bottleneck else None,
        "bottleneck_pending_qty": int(bottleneck.pending_qty or 0) if bottleneck else 0,
    }


async def _find_po(po_number: str) -> PurchaseOrder | None:
    session = current_session()
    ref = po_number.strip()
    if not ref:
        return None
    compact = ref.upper().replace(" ", "")
    result = await session.execute(
        select(PurchaseOrder)
        .where(
            or_(
                func.upper(PurchaseOrder.po_number) == compact,
                func.upper(PurchaseOrder.po_number) == ref.upper(),
                PurchaseOrder.po_number.ilike(f"%{ref}%"),
                PurchaseOrder.design_code_snapshot.ilike(f"%{ref}%"),
            )
        )
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
            selectinload(PurchaseOrder.dispatch_loads),
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    po = result.scalars().first()
    if po is None:
        return None
    await ensure_po_operational_data(session, po)
    result = await session.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == po.id)
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
            selectinload(PurchaseOrder.dispatch_loads),
        )
    )
    return result.scalar_one_or_none()


@tool()
async def list_pending_purchase_orders(blocker: str = "all", month: str = "") -> dict:
    """List purchase orders that need owner attention from the real database.

    Args:
        blocker: Optional filter. Use "all", "fabric_shortage", "delayed",
            "dispatch_pending", or a stage name like "cutting", "stitching",
            "finishing"/"quality_check", "packing".
        month: Optional month name, e.g. "June". Empty string means all months.

    Returns:
        A dict with count and pending_pos. Each PO summary includes po_number,
        product, quantity_pieces, shipment_date, status, pending_qty,
        shortage_meters, bottleneck_stage, and bottleneck_pending_qty.
    """
    session = current_session()
    await ensure_all_operational_data(session)
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
            selectinload(PurchaseOrder.dispatch_loads),
        )
        .order_by(PurchaseOrder.promise_delivery_date.asc(), PurchaseOrder.po_number.asc())
    )
    rows = []
    month_num = _month_number(month)
    normalized_blocker = blocker.strip().lower().replace(" ", "_") or "all"
    stage_alias = {"finishing": "quality_check", "finish": "quality_check"}
    normalized_blocker = stage_alias.get(normalized_blocker, normalized_blocker)
    today = date.today()
    for po in result.scalars().all():
        if month_num and po.promise_delivery_date.month != month_num and po.order_date.month != month_num:
            continue
        summary = _po_summary(po)
        if normalized_blocker == "fabric_shortage" and summary["shortage_meters"] <= 0:
            continue
        if normalized_blocker == "delayed" and not (po.promise_delivery_date < today and summary["pending_qty"] > 0):
            continue
        if normalized_blocker == "dispatch_pending":
            dispatch = next((stage for stage in po.stage_summaries if stage.stage.value == "dispatch"), None)
            if po.status in _TERMINAL or dispatch is None or dispatch.pending_qty <= 0:
                continue
        if normalized_blocker not in {"all", "fabric_shortage", "delayed", "dispatch_pending"}:
            stage = next((item for item in po.stage_summaries if item.stage.value == normalized_blocker), None)
            if stage is None or stage.pending_qty <= 0:
                continue
        if normalized_blocker == "all" and po.status in _TERMINAL:
            continue
        rows.append(summary)
    return {"count": len(rows), "pending_pos": rows[:100], "truncated": len(rows) > 100}


@tool()
async def get_po_status(po_number: str) -> dict:
    """Look up a single purchase order by PO number or design/fabric code.

    Args:
        po_number: Full or partial PO number, e.g.
            "109-MINI-FERN-140X215-PL-RS7-10-26".

    Returns:
        A dict with found, PO summary, stage_summaries, contractor_allocations,
        and fabric_plan. No sample data is returned.
    """
    session = current_session()
    po = await _find_po(po_number)
    if po is None:
        return {"found": False, "po_number": po_number}
    allocations_result = await session.execute(
        select(ContractorAllocation)
        .join(StageSummary, StageSummary.id == ContractorAllocation.stage_summary_id)
        .where(StageSummary.purchase_order_id == po.id)
        .options(selectinload(ContractorAllocation.contractor))
        .order_by(ContractorAllocation.created_at.desc())
    )
    allocations = []
    for item in allocations_result.scalars().all():
        allocations.append(
            {
                "stage": item.stage.value,
                "contractor": item.contractor.name if item.contractor else None,
                "issued_qty": int(item.issued_qty or 0),
                "completed_qty": int(item.completed_qty or 0),
                "pending_qty": max(int(item.issued_qty or 0) - int(item.completed_qty or 0), 0),
                "expected_completion_date": item.expected_completion_date.isoformat() if item.expected_completion_date else None,
                "delay_days": int(item.delay_days or 0),
            }
        )
    fabric_plan = None
    if po.fabric_plan is not None:
        fabric_plan = {
            "required_m": _to_float(po.fabric_plan.required_m),
            "wastage_m": _to_float(po.fabric_plan.wastage_m),
            "total_required_m": _to_float(po.fabric_plan.total_required_m),
            "available_m": _to_float(po.fabric_plan.available_m),
            "shortage_m": _to_float(po.fabric_plan.shortage_m),
            "status": po.fabric_plan.status.value,
        }
    return {
        "found": True,
        "po": _po_summary(po),
        "fabric_plan": fabric_plan,
        "stage_summaries": [_stage_payload(stage) for stage in po.stage_summaries],
        "contractor_allocations": allocations,
    }


def _month_number(month: str) -> int | None:
    value = month.strip().lower()
    if not value:
        return None
    names = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }
    if value.isdigit() and 1 <= int(value) <= 12:
        return int(value)
    return names.get(value)


@tool(requires_confirmation=True)
async def update_po_notes(po_number: str, note: str, confirmed: bool = False) -> dict:
    """Append a note (free-text) to an existing purchase order.

    CONFIRMATION REQUIRED: first call with confirmed=False to preview what
    would change. After the owner says yes, call again with confirmed=True.
    """
    session = current_session()
    note = note.strip()
    if not note:
        return {"error": "note must not be empty", "po_number": po_number}

    result = await session.execute(
        select(PurchaseOrder).where(func.lower(PurchaseOrder.po_number) == po_number.strip().lower())
    )
    po = result.scalar_one_or_none()
    if po is None:
        return {"found": False, "po_number": po_number}

    existing = (po.notes or "").rstrip()
    new_notes = f"{existing}\n{note}".strip() if existing else note

    if not confirmed:
        return {
            "requires_confirmation": True,
            "preview": f"Append this note to {po.po_number}: '{note}'.",
            "po_number": po.po_number,
            "note_to_append": note,
            "current_notes": po.notes,
        }

    po.notes = new_notes
    await session.commit()
    return {"done": True, "po_number": po.po_number, "notes": new_notes}
