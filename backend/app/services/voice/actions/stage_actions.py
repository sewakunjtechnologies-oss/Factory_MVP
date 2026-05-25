"""Stage progress write tool — Phase 2 follow-up.

Records a daily `StageProgressEntry` against the StageSummary for a given PO + stage.
We also bump the StageSummary running totals so dashboards stay in sync without
needing a separate aggregation step.

IMPORTANT: no `from __future__ import annotations` (breaks Gemini auto FC).
"""

from datetime import date as _date

from sqlalchemy import select

from app.models.enums import StageName, StageStatus
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageProgressEntry, StageSummary
from sqlalchemy import func

from ..db_context import current_session
from ..tools import tool


_VALID_STAGES = {s.value for s in StageName}


@tool(requires_confirmation=True)
async def record_stage_progress(
    po_number: str,
    stage: str,
    approved_today: int = 0,
    rejected_today: int = 0,
    remarks: str = "",
    confirmed: bool = False,
) -> dict:
    """Record today's progress at a specific workflow stage for a PO. Use this
    when the owner reports pieces completed, approved, or rejected at a stage —
    e.g. "500 pieces approved at cutting for PO-2026-0042" or "30 pieces rejected
    in QC for PO-0048". Creates one StageProgressEntry for today and updates
    the running StageSummary totals.

    CONFIRMATION REQUIRED: first call with confirmed=False to preview. After the
    owner says yes, call again with confirmed=True.

    Args:
        po_number: PO this progress belongs to, e.g. "PO-2026-0042".
        stage: One of "fabric_ready", "cutting", "stitching", "size_inspection",
            "quality_check", "packing", "dispatch".
        approved_today: Pieces approved at this stage today. Must be >= 0.
        rejected_today: Pieces rejected at this stage today. Must be >= 0.
        remarks: Optional free-text notes for the entry. Empty string by default.
        confirmed: Owner has explicitly approved. Default False returns a preview.

    Returns:
        A dict. confirmed=False: {requires_confirmation, preview, po_number,
        stage, approved_today, rejected_today, remarks}. confirmed=True:
        {done: True, entry_id, po_number, stage, approved_today, rejected_today,
        new_summary_totals}. Error variants: {found: False} or {error, ...}.
    """
    session = current_session()

    stage_norm = stage.strip().lower()
    if stage_norm not in _VALID_STAGES:
        return {
            "error": "invalid stage name",
            "value_received": stage,
            "valid_stages": sorted(_VALID_STAGES),
        }
    if approved_today < 0 or rejected_today < 0:
        return {
            "error": "approved_today and rejected_today must be >= 0",
            "approved_today": approved_today,
            "rejected_today": rejected_today,
        }
    if approved_today == 0 and rejected_today == 0:
        return {"error": "nothing to record — approved_today and rejected_today are both 0"}

    po_result = await session.execute(
        select(PurchaseOrder).where(func.lower(PurchaseOrder.po_number) == po_number.lower())
    )
    po = po_result.scalar_one_or_none()
    if po is None:
        return {"found": False, "po_number": po_number}

    summary_result = await session.execute(
        select(StageSummary).where(
            StageSummary.purchase_order_id == po.id,
            StageSummary.stage == StageName(stage_norm),
        )
    )
    summary = summary_result.scalar_one_or_none()
    if summary is None:
        return {
            "error": "no StageSummary exists for this PO+stage yet — create it from the workflow setup first",
            "po_number": po.po_number,
            "stage": stage_norm,
        }

    if not confirmed:
        parts = []
        if approved_today:
            parts.append(f"{approved_today} approved")
        if rejected_today:
            parts.append(f"{rejected_today} rejected")
        return {
            "requires_confirmation": True,
            "preview": (
                f"Record today's progress at {stage_norm} for {po.po_number}: "
                f"{', '.join(parts)}."
            ),
            "po_number": po.po_number,
            "stage": stage_norm,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
            "remarks": remarks,
        }

    entry = StageProgressEntry(
        stage_summary_id=summary.id,
        entry_date=_date.today(),
        approved_today=approved_today,
        rejected_today=rejected_today,
        completed_today=approved_today + rejected_today,
        remarks=remarks.strip() or None,
    )
    session.add(entry)
    summary.approved_qty = (summary.approved_qty or 0) + approved_today
    summary.rejected_qty = (summary.rejected_qty or 0) + rejected_today
    summary.completed_qty = (summary.completed_qty or 0) + approved_today + rejected_today
    if summary.status == StageStatus.not_started and (approved_today + rejected_today) > 0:
        summary.status = StageStatus.in_progress
    await session.commit()
    await session.refresh(entry)
    await session.refresh(summary)

    return {
        "done": True,
        "entry_id": str(entry.id),
        "po_number": po.po_number,
        "stage": stage_norm,
        "approved_today": approved_today,
        "rejected_today": rejected_today,
        "new_summary_totals": {
            "approved_qty": int(summary.approved_qty or 0),
            "rejected_qty": int(summary.rejected_qty or 0),
            "completed_qty": int(summary.completed_qty or 0),
            "status": summary.status.value if hasattr(summary.status, "value") else str(summary.status),
        },
    }
