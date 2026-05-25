from __future__ import annotations

from datetime import date
from typing import Any

from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_daily_factory_summary_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    today = date.today()
    pos = await access.list_pos()
    delayed_count = 0
    active_count = 0
    for po in pos:
        approved = max([stage.approved_qty for stage in po.stage_summaries] + [0])
        if approved < po.order_quantity_pcs:
            active_count += 1
        if po.promise_delivery_date < today and approved < po.order_quantity_pcs:
            delayed_count += 1

    shortages = await access.get_shortage_plans()
    dispatch_ready = await access.get_dispatch_ready_rows()
    urgent_alerts = [item for item in await access.get_open_alerts() if item.priority.value in {"critical", "high"}]
    reminders = await access.get_open_reminders()

    rows = [
        {"metric": "Active POs", "value": active_count},
        {"metric": "Delayed POs", "value": delayed_count},
        {"metric": "Fabric Shortage POs", "value": len(shortages)},
        {"metric": "Dispatch Ready POs", "value": len(dispatch_ready)},
        {"metric": "Critical/High Alerts", "value": len(urgent_alerts)},
        {"metric": "Open Reminders", "value": len(reminders)},
        {"metric": "Report Date", "value": format_date(today)},
    ]

    return ReportPayload(
        title="Daily Factory Summary Report",
        summary={
            "active_pos": active_count,
            "delayed_pos": delayed_count,
            "fabric_shortages": len(shortages),
            "dispatch_ready_pos": len(dispatch_ready),
        },
        rows=rows,
        recommendations=[
            "Focus today on delayed POs and unresolved shortages.",
            "Convert dispatch-ready POs into confirmed loads before cut-off.",
        ],
    )


async def generate_urgent_actions_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    rows = []
    for alert in await access.get_open_alerts():
        if alert.priority.value not in {"critical", "high"}:
            continue
        rows.append(
            {
                "source": "alert",
                "priority": alert.priority.value,
                "title": alert.title,
                "message": alert.message,
                "po_number": alert.purchase_order.po_number if alert.purchase_order else "-",
            }
        )
    for reminder in await access.get_open_reminders():
        if reminder.priority.value not in {"critical", "high"}:
            continue
        rows.append(
            {
                "source": "reminder",
                "priority": reminder.priority.value,
                "title": reminder.title,
                "message": reminder.message,
                "po_number": reminder.purchase_order.po_number if reminder.purchase_order else "-",
            }
        )
    rows.sort(key=lambda item: item.get("priority") != "critical")
    return ReportPayload(
        title="Urgent Actions Report",
        summary={"urgent_items": len(rows)},
        rows=rows,
        recommendations=["Assign each urgent item to a clear owner and target completion time."],
    )


async def generate_owner_review_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    summary_payload = await generate_daily_factory_summary_report(access, filters)
    urgent_payload = await generate_urgent_actions_report(access, filters)
    rows = []
    rows.extend(summary_payload.rows)
    rows.append({"metric": "-----", "value": "-----"})
    for row in urgent_payload.rows[:20]:
        rows.append(
            {
                "metric": f"{row.get('priority', '').upper()} {row.get('source', '').title()}",
                "value": f"{row.get('title')} ({row.get('po_number')})",
            }
        )
    return ReportPayload(
        title="Owner Review Report",
        summary={
            "active_pos": summary_payload.summary.get("active_pos", 0),
            "urgent_items": urgent_payload.summary.get("urgent_items", 0),
        },
        rows=rows,
        recommendations=[
            "Review top urgent actions and close blockers before end-of-day.",
            "Escalate late mills and delayed contractors immediately.",
        ],
    )

