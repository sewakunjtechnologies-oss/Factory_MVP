from __future__ import annotations

from datetime import date
from typing import Any

from app.services.pdf_reports.data_access import FactoryAIDataAccess, decimal_to_float
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_mill_orders_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    po_filter = str(filters.get("po_number") or "").strip()
    mill_filter = str(filters.get("mill") or filters.get("mill_name") or "").strip().lower()
    po = await access.find_po(po_filter) if po_filter else None
    rows = []
    for order in await access.get_mill_orders(po.id if po else None):
        if mill_filter and mill_filter not in order.mill_name.lower():
            continue
        rows.append(
            {
                "mill_name": order.mill_name,
                "po_id": str(order.purchase_order_id),
                "ordered_meters": decimal_to_float(order.ordered_meters),
                "ordered_gsm": decimal_to_float(order.ordered_gsm) if order.ordered_gsm is not None else "-",
                "committed_delivery_date": format_date(order.committed_delivery_date),
                "actual_delivery_date": format_date(order.actual_delivery_date),
                "status": order.status.value,
            }
        )
    return ReportPayload(
        title="Mill Orders Report",
        summary={"mill_orders": len(rows)},
        rows=rows,
        recommendations=["Follow up overdue and partial mill orders first."],
    )


async def generate_late_mill_deliveries_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    report_date = date.today()
    rows = []
    late_orders = await access.get_late_mill_orders(report_date)
    for order in late_orders:
        rows.append(
            {
                "mill_name": order.mill_name,
                "po_id": str(order.purchase_order_id),
                "committed_delivery_date": format_date(order.committed_delivery_date),
                "actual_delivery_date": format_date(order.actual_delivery_date),
                "status": order.status.value,
                "ordered_meters": decimal_to_float(order.ordered_meters),
            }
        )
    return ReportPayload(
        title="Late Mill Deliveries Report",
        summary={"late_mill_orders": len(rows)},
        rows=rows,
        recommendations=["Escalate mills with missed dates and open shortage risk."],
    )

