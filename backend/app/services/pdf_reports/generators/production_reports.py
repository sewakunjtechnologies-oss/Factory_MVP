from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageProgressEntry, StageSummary
from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators import format_date, parse_iso_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_daily_production_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    on_date = parse_iso_date(filters.get("date_from")) or date.today()
    statement = (
        select(StageProgressEntry, StageSummary, PurchaseOrder)
        .join(StageSummary, StageSummary.id == StageProgressEntry.stage_summary_id)
        .join(PurchaseOrder, PurchaseOrder.id == StageSummary.purchase_order_id)
        .where(StageProgressEntry.entry_date == on_date)
        .order_by(PurchaseOrder.po_number.asc(), StageSummary.stage.asc())
    )
    result = await access.db.execute(statement)
    rows = []
    total_completed = 0
    total_approved = 0
    total_moved = 0
    for entry, stage_summary, po in result.all():
        total_completed += entry.completed_today
        total_approved += entry.approved_today
        total_moved += entry.moved_to_next_stage_today
        rows.append(
            {
                "po_number": po.po_number,
                "stage": stage_summary.stage.value,
                "date": format_date(entry.entry_date),
                "completed": entry.completed_today,
                "approved": entry.approved_today,
                "rejected": entry.rejected_today,
                "repair": entry.repair_today,
                "alter": entry.alter_today,
                "moved_forward": entry.moved_to_next_stage_today,
            }
        )
    return ReportPayload(
        title=f"Daily Production Report - {on_date.isoformat()}",
        summary={
            "entries": len(rows),
            "total_completed": total_completed,
            "total_approved": total_approved,
            "total_moved_forward": total_moved,
        },
        rows=rows,
        recommendations=["Ensure stage movement is aligned with approved quantity."],
    )


async def generate_stage_progress_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    stage_filter = str(filters.get("stage") or "").strip().lower()
    pos = await access.list_pos()
    rows = []
    for po in pos:
        for stage in po.stage_summaries:
            if stage_filter and stage_filter != stage.stage.value.lower():
                continue
            rows.append(
                {
                    "po_number": po.po_number,
                    "stage": stage.stage.value,
                    "status": stage.status.value,
                    "input_qty": stage.input_qty,
                    "approved_qty": stage.approved_qty,
                    "pending_qty": stage.pending_qty,
                    "moved_to_next_qty": stage.moved_to_next_qty,
                }
            )
    return ReportPayload(
        title="Stage Progress Report",
        summary={"stage_rows": len(rows), "stage_filter": stage_filter or "all"},
        rows=rows,
        recommendations=["Focus on stages with high pending quantities and low movement."],
    )

