from __future__ import annotations

from typing import Any

from app.services.pdf_reports.data_access import FactoryAIDataAccess, decimal_to_float
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_pending_dispatch_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    pos = await access.list_pos()
    for po in pos:
        packing = next((stage for stage in po.stage_summaries if stage.stage.value == "packing"), None)
        if packing is None:
            continue
        dispatched = sum(load.shipped_qty for load in po.dispatch_loads)
        pending = max(packing.approved_qty - dispatched, 0)
        if pending <= 0:
            continue
        rows.append(
            {
                "po_number": po.po_number,
                "product": po.product.product_name if po.product else "Product",
                "ready_qty": packing.approved_qty,
                "dispatched_qty": dispatched,
                "pending_dispatch_qty": pending,
                "deadline": format_date(po.promise_delivery_date),
                "status": po.status.value,
            }
        )
    return ReportPayload(
        title="Pending Dispatch Report",
        summary={"pending_dispatch_pos": len(rows)},
        rows=rows,
        recommendations=["Prioritize pending dispatch by nearest deadline and highest ready quantity."],
    )


async def generate_dispatch_ready_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    ready_rows = await access.get_dispatch_ready_rows()
    rows = []
    for row in ready_rows:
        rows.append(
            {
                "po_number": row["po_number"],
                "product": row["product"],
                "ready_qty": row["ready_qty"],
                "shipped_qty": row["shipped_qty"],
                "deadline": format_date(row["promise_delivery_date"]),
                "documentation_status": row["documentation_status"],
            }
        )
    return ReportPayload(
        title="Dispatch Ready POs Report",
        summary={"dispatch_ready_pos": len(rows)},
        rows=rows,
        recommendations=["Create dispatch loads for urgent POs first."],
    )


async def generate_dispatch_cost_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    cost_type_filter = str(filters.get("status") or filters.get("cost_type") or "").strip().lower()
    rows = []
    total_cost = 0.0
    total_qty = 0
    for load in await access.get_dispatch_loads():
        if cost_type_filter and load.cost_type.value.lower() != cost_type_filter:
            continue
        dispatch_cost = decimal_to_float(load.dispatch_cost)
        total_cost += dispatch_cost
        total_qty += load.shipped_qty
        rows.append(
            {
                "load_number": load.load_number,
                "po_id": str(load.purchase_order_id),
                "date": format_date(load.shipped_at),
                "cost_type": load.cost_type.value,
                "shipped_qty": load.shipped_qty,
                "dispatch_cost": dispatch_cost,
                "cost_per_piece": decimal_to_float(load.cost_per_piece),
                "transporter": load.transporter_name or "-",
            }
        )
    summary = {
        "dispatch_loads": len(rows),
        "total_dispatch_cost": round(total_cost, 2),
        "total_shipped_qty": total_qty,
        "average_cost_per_piece": round((total_cost / total_qty), 4) if total_qty > 0 else 0,
    }
    return ReportPayload(
        title="Dispatch Cost Report",
        summary=summary,
        rows=rows,
        recommendations=["Review high cost-per-piece loads and optimize transporter/cost type mix."],
    )

