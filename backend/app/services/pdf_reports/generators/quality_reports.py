from __future__ import annotations

from typing import Any

from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_qc_failures_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    failures = await access.get_quality_failures()
    for row in failures:
        rows.append(
            {
                "stage_summary_id": str(row.stage_summary_id),
                "action_date": format_date(row.action_date),
                "failed_qty": row.failed_qty,
                "resolved_qty": row.resolved_qty,
                "pending_resolution_qty": row.pending_resolution_qty,
                "action": row.action.value,
                "reason": row.reason,
            }
        )
    return ReportPayload(
        title="Quantity Shortfall Report",
        summary={"shortfalls": len(rows)},
        rows=rows,
        recommendations=["Resolve pending quantity shortfalls before dispatch deadlines."],
    )


async def generate_qc_inspection_report(_: FactoryAIDataAccess, __: dict[str, Any]) -> ReportPayload:
    # QC inspections were removed in the 2026-05-15 workflow simplification.
    # Verification at fabric receipt and stitched-product return now happens in
    # stage_summaries + fabric_receipts directly.
    return ReportPayload(
        title="QC Inspection Report",
        summary={"inspections": 0},
        rows=[],
        recommendations=["QC inspections are no longer tracked separately. Use stage progress instead."],
    )
