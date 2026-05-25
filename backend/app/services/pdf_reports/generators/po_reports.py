from __future__ import annotations

from datetime import date
from typing import Any

from app.models.enums import POStatus
from app.services.pdf_reports.calculators import completion_percentage
from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators import format_date, parse_iso_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_running_pos_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    rows = []
    pos = await access.list_pos()
    for po in pos:
        if po.status in {POStatus.completed, POStatus.cancelled}:
            continue
        approved = 0
        if po.stage_summaries:
            approved = max(stage.approved_qty for stage in po.stage_summaries)
        rows.append(
            {
                "po_number": po.po_number,
                "product": po.product.product_name if po.product else "Product",
                "status": po.status.value,
                "design_name": po.design_name_snapshot,
                "design_code": po.design_code_snapshot,
                "design_image_url": po.design_image_url_snapshot,
                "design_status": po.design_status.value if po.design_status else "not_provided",
                "order_qty": po.order_quantity_pcs,
                "approved_qty": approved,
                "pending_qty": max(po.order_quantity_pcs - approved, 0),
                "dispatch_deadline": format_date(po.promise_delivery_date),
            }
        )
    return ReportPayload(
        title="Running POs Report",
        summary={"running_pos": len(rows)},
        rows=rows,
        recommendations=["Prioritize delayed and near-deadline POs first."],
    )


async def generate_delayed_pos_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    rows = []
    today = parse_iso_date(filters.get("date_to")) or date.today()
    pos = await access.list_pos()
    for po in pos:
        approved = 0
        if po.stage_summaries:
            approved = max(stage.approved_qty for stage in po.stage_summaries)
        if po.promise_delivery_date < today and approved < po.order_quantity_pcs:
            rows.append(
                {
                    "po_number": po.po_number,
                    "product": po.product.product_name if po.product else "Product",
                    "dispatch_deadline": format_date(po.promise_delivery_date),
                    "design_name": po.design_name_snapshot,
                    "design_code": po.design_code_snapshot,
                    "design_status": po.design_status.value if po.design_status else "not_provided",
                    "pending_qty": max(po.order_quantity_pcs - approved, 0),
                    "status": po.status.value,
                }
            )
    return ReportPayload(
        title="Delayed POs Report",
        summary={"delayed_pos": len(rows)},
        rows=rows,
        recommendations=["Follow up owner/manager for immediate recovery plan on delayed POs."],
    )


async def generate_po_status_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    po_ref = str(filters.get("po_number") or filters.get("po_reference") or "").strip()
    po = await access.find_po(po_ref) if po_ref else None
    if po is None:
        return ReportPayload(
            title="PO Status Report",
            summary={"po_found": False},
            rows=[],
            recommendations=["No records found. Provide a valid PO number like PO-2026-001."],
        )
    rows = []
    for stage in po.stage_summaries:
        rows.append(
            {
                "stage": stage.stage.value,
                "status": stage.status.value,
                "input_qty": stage.input_qty,
                "approved_qty": stage.approved_qty,
                "pending_qty": stage.pending_qty,
            }
        )
    approved = max([stage.approved_qty for stage in po.stage_summaries] + [0])
    payload = ReportPayload(
        title=f"PO Status Report - {po.po_number}",
        summary={
            "po_number": po.po_number,
            "product": po.product.product_name if po.product else "Product",
                "status": po.status.value,
                "design_name": po.design_name_snapshot,
                "design_code": po.design_code_snapshot,
                "design_image_url": po.design_image_url_snapshot,
                "design_status": po.design_status.value if po.design_status else "not_provided",
                "completion_percentage": round(completion_percentage(approved, po.order_quantity_pcs), 2),
            "dispatch_deadline": format_date(po.promise_delivery_date),
        },
        rows=rows,
        recommendations=["Track bottleneck stage and clear pending movement daily."],
    )
    return payload


async def generate_po_stage_progress_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    po_ref = str(filters.get("po_number") or filters.get("po_reference") or "").strip()
    po = await access.find_po(po_ref) if po_ref else None
    if po is None:
        return ReportPayload(
            title="PO Stage Progress Report",
            summary={"po_found": False},
            rows=[],
            recommendations=["No records found. Provide a valid PO number."],
        )
    progress_rows = []
    entries = await access.get_stage_progress_entries(po.id)
    for entry in entries:
        progress_rows.append(
            {
                "date": format_date(entry.entry_date),
                "stage_summary_id": str(entry.stage_summary_id),
                "completed": entry.completed_today,
                "approved": entry.approved_today,
                "rejected": entry.rejected_today,
                "repair": entry.repair_today,
                "alter": entry.alter_today,
                "moved_forward": entry.moved_to_next_stage_today,
            }
        )
    return ReportPayload(
        title=f"PO Stage Progress Report - {po.po_number}",
        summary={"progress_entries": len(progress_rows)},
        rows=progress_rows,
        recommendations=["Ensure moved forward quantity does not exceed approved availability."],
    )
