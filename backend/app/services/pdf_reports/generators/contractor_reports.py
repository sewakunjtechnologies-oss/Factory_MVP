from __future__ import annotations

from typing import Any

from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_contractor_delay_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    contractor_filter = str(filters.get("contractor") or filters.get("factor_name") or "").strip().lower()
    rows = []
    delayed = await access.get_delayed_allocations()
    for item in delayed:
        contractor_name = item.contractor.name if item.contractor else "-"
        if contractor_filter and contractor_filter not in contractor_name.lower():
            continue
        pending = max(item.issued_qty - item.completed_qty, 0)
        rows.append(
            {
                "contractor": contractor_name,
                "stage": item.stage.value,
                "issued_qty": item.issued_qty,
                "completed_qty": item.completed_qty,
                "pending_qty": pending,
                "target_date": format_date(item.expected_completion_date),
                "status": "delayed",
            }
        )
    return ReportPayload(
        title="Contractor Delay Report",
        summary={"delayed_allocations": len(rows)},
        rows=rows,
        recommendations=["Contact delayed contractors and re-balance pending quantity where required."],
    )


async def generate_contractor_performance_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    rows = []
    allocations = await access.get_delayed_allocations()
    for item in allocations:
        contractor_name = item.contractor.name if item.contractor else "-"
        issued = max(item.issued_qty, 1)
        completed_ratio = round((item.completed_qty / issued) * 100, 2)
        rows.append(
            {
                "contractor": contractor_name,
                "stage": item.stage.value,
                "issued_qty": item.issued_qty,
                "completed_qty": item.completed_qty,
                "completion_percent": completed_ratio,
                "delay_days": item.delay_days,
            }
        )
    rows.sort(key=lambda item: (item.get("delay_days", 0), -item.get("completion_percent", 0)), reverse=True)
    return ReportPayload(
        title="Contractor Performance Report",
        summary={"contractors": len(rows)},
        rows=rows,
        recommendations=["Review low completion and high delay contractors first."],
    )

