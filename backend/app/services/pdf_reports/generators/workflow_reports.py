from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.fabric import FabricIssueToCutting, MillDeliveryLot, MillOrderSplit
from app.models.reminder import Reminder
from app.services.pdf_reports.data_access import FactoryAIDataAccess, decimal_to_float
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_mill_order_split_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    result = await access.db.execute(select(MillOrderSplit).order_by(MillOrderSplit.created_at.desc()))
    rows = [
        {
            "po_id": str(item.purchase_order_id),
            "mill_name": item.mill_name,
            "split_percent": float(item.split_percent),
            "ordered_meters": decimal_to_float(item.ordered_meters),
            "committed_delivery_date": format_date(item.committed_delivery_date),
            "status": item.status.value,
        }
        for item in result.scalars().all()
    ]
    return ReportPayload(title="Mill Order Split Report", summary={"split_rows": len(rows)}, rows=rows, recommendations=["Verify split totals and follow up late mills."])


async def generate_partial_mill_delivery_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    result = await access.db.execute(select(MillDeliveryLot).order_by(MillDeliveryLot.received_date.desc()))
    rows = [
        {
            "mill_order_id": str(item.fabric_mill_order_id),
            "lot_number": item.lot_number,
            "delivered_meters": decimal_to_float(item.delivered_meters),
            "received_date": format_date(item.received_date),
            "status": item.status.value,
        }
        for item in result.scalars().all()
    ]
    return ReportPayload(title="Partial Mill Delivery Report", summary={"delivery_lots": len(rows)}, rows=rows, recommendations=["Close partial deliveries with follow-up reminders."])


async def generate_fabric_verification_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    for receipt in await access.get_fabric_verification_pending():
        rows.append(
            {
                "receipt_id": str(receipt.id),
                "supplier": receipt.supplier_name,
                "verification_status": receipt.verification_status.value,
                "verified_by": str(receipt.verified_by) if receipt.verified_by else "-",
                "verification_date": format_date(receipt.verification_date),
            }
        )
    return ReportPayload(title="Fabric Verification Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Clear pending verifications to unblock allocations."])


async def generate_fabric_mismatch_review_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    for receipt in await access.get_fabric_mismatch_issues():
        rows.append(
            {
                "receipt_id": str(receipt.id),
                "supplier": receipt.supplier_name,
                "status": receipt.verification_status.value,
                "mismatch_reason": receipt.mismatch_reason or "-",
                "action_taken": receipt.action_taken.value if receipt.action_taken else "-",
            }
        )
    return ReportPayload(title="Fabric Mismatch / Override Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Owner should review accepted mismatches and repeated suppliers."])


async def generate_fabric_allocation_to_cutting_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    result = await access.db.execute(select(FabricIssueToCutting).order_by(FabricIssueToCutting.issue_date.desc()))
    rows = [
        {
            "po_id": str(item.purchase_order_id),
            "issued_meters": decimal_to_float(item.issued_meters),
            "issue_date": format_date(item.issue_date),
            "expected_return_date": format_date(item.expected_return_date),
            "status": item.status or "issued",
        }
        for item in result.scalars().all()
    ]
    return ReportPayload(title="Fabric Allocation To Cutting Report", summary={"allocations": len(rows)}, rows=rows, recommendations=["Track pending cutting returns against expected dates."])


async def generate_cutting_wastage_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    for item in await access.list_cutting_analysis():
        rows.append(
            {
                "po_id": str(item.purchase_order_id),
                "planned_wastage_m": float(item.planned_wastage_m),
                "actual_wastage_m": float(item.actual_wastage_m),
                "wastage_difference_m": float(item.wastage_difference_m),
            }
        )
    return ReportPayload(title="Cutting Wastage Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Investigate high positive wastage differences by mill and contractor."])


async def generate_stitching_verification_report(_: FactoryAIDataAccess, __: dict[str, Any]) -> ReportPayload:
    # QC inspections were removed in the workflow simplification (2026-05-15).
    # Stitching verification now flows through stage_summaries directly.
    return ReportPayload(title="Stitching Verification Report", summary={"rows": 0}, rows=[], recommendations=["Use the production page to check stitching status."])


async def generate_repair_rework_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    for item in await access.get_quality_failures():
        rows.append(
            {
                "stage_summary_id": str(item.stage_summary_id),
                "failed_qty": item.failed_qty,
                "resolved_qty": item.resolved_qty,
                "pending_resolution_qty": item.pending_resolution_qty,
                "action": item.action.value,
                "reason": item.reason,
            }
        )
    return ReportPayload(title="Repair / Rework Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Close pending resolutions and return approved rework to stage flow."])


async def generate_dispatch_documentation_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    for item in await access.get_dispatch_loads():
        rows.append(
            {
                "load_number": item.load_number,
                "po_id": str(item.purchase_order_id),
                "document_status": item.document_status or "pending",
                "invoice_uploaded": item.invoice_uploaded,
                "packing_list_uploaded": item.packing_list_uploaded,
                "eway_bill_uploaded": item.eway_bill_uploaded,
                "transporter_confirmation": item.transporter_confirmation,
            }
        )
    return ReportPayload(title="Dispatch Documentation Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Complete blocked or pending document rows before dispatch cut-off."])


async def generate_dispatch_exception_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    for item in await access.get_dispatch_loads():
        if item.shortfall_qty <= 0:
            continue
        rows.append(
            {
                "load_number": item.load_number,
                "po_id": str(item.purchase_order_id),
                "shortfall_qty": item.shortfall_qty,
                "shortfall_reason": item.shortfall_reason or "-",
                "linked_repair_qty": item.linked_repair_qty,
                "linked_alteration_qty": item.linked_alteration_qty,
            }
        )
    return ReportPayload(title="Dispatch Exception Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Resolve shortfall through rework closure or buyer-approved exception."])


async def generate_role_pending_tasks_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    for item in await access.get_open_reminders():
        rows.append(
            {
                "role": "assigned",
                "title": item.title,
                "type": item.reminder_type.value,
                "due_date": format_date(item.due_date),
                "priority": item.priority.value,
            }
        )
    return ReportPayload(title="Role-wise Pending Task Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Reassign overdue tasks where assignees are unavailable."])


async def generate_escalated_reminders_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    result = await access.db.execute(select(Reminder).where(Reminder.escalation_level > 0).order_by(Reminder.escalated_at.desc()))
    rows = [
        {
            "id": str(item.id),
            "title": item.title,
            "escalation_level": item.escalation_level,
            "escalated_to": str(item.escalated_to) if item.escalated_to else "-",
            "escalated_at": format_date(item.escalated_at),
            "due_date": format_date(item.due_date),
        }
        for item in result.scalars().all()
    ]
    return ReportPayload(title="Escalated Reminders Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Owner should review root causes for repeated escalations."])


async def generate_buyer_return_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    result = await access.db.execute(
        select(AuditLog)
        .where(AuditLog.action_type == "buyer_return_recorded")
        .order_by(AuditLog.created_at.desc())
    )
    rows = [
        {
            "po_id": str(item.purchase_order_id) if item.purchase_order_id else "-",
            "entity_id": item.entity_id,
            "remarks": item.remarks or "-",
            "created_at": format_date(item.created_at),
        }
        for item in result.scalars().all()
    ]
    return ReportPayload(title="Buyer Return Report", summary={"rows": len(rows)}, rows=rows, recommendations=["Reopen issues for buyer returns and track closure cycle."])

