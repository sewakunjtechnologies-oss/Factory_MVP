from __future__ import annotations

from typing import Any

from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_alerts_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    priority_filter = str(filters.get("priority") or "").strip().lower()
    rows = []
    for alert in await access.get_open_alerts():
        if priority_filter and alert.priority.value.lower() != priority_filter:
            continue
        po_number = alert.purchase_order.po_number if alert.purchase_order else "-"
        rows.append(
            {
                "priority": alert.priority.value,
                "type": alert.alert_type.value,
                "title": alert.title,
                "message": alert.message,
                "po_number": po_number,
                "created_at": format_date(alert.created_at),
                "status": "resolved" if alert.is_resolved else "open",
            }
        )
    rows.sort(key=lambda item: (item.get("priority") != "critical", item.get("priority") != "high"))
    return ReportPayload(
        title="Alerts Report",
        summary={"open_alerts": len(rows)},
        rows=rows,
        recommendations=["Resolve critical alerts first and assign owners for open high-priority items."],
    )


async def generate_reminders_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    rows = []
    for reminder in await access.get_open_reminders():
        po_number = reminder.purchase_order.po_number if reminder.purchase_order else "-"
        rows.append(
            {
                "po_number": po_number,
                "type": reminder.reminder_type.value,
                "title": reminder.title,
                "message": reminder.message,
                "priority": reminder.priority.value,
                "due_date": format_date(reminder.due_date),
                "status": reminder.status.value,
            }
        )
    rows.sort(key=lambda item: (item.get("priority") != "critical", item.get("due_date")))
    return ReportPayload(
        title="Reminders Report",
        summary={"open_reminders": len(rows)},
        rows=rows,
        recommendations=["Clear overdue reminders and set explicit assignees for today."],
    )

