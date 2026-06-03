from __future__ import annotations

from datetime import date
from typing import Any

from app.models.enums import POStatus
from app.services.pdf_reports.data_access import FactoryAIDataAccess, decimal_to_float
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_pending_dispatch_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    pos = await access.list_pos()
    for po in pos:
        if po.status in {POStatus.completed, POStatus.cancelled}:
            continue
        packing = next((stage for stage in po.stage_summaries if stage.stage.value == "packing"), None)
        if packing is None:
            continue
        dispatch_stage = next((stage for stage in po.stage_summaries if stage.stage.value == "dispatch"), None)
        dispatched = max(
            sum(load.shipped_qty for load in po.dispatch_loads),
            int(dispatch_stage.completed_qty or 0) if dispatch_stage else 0,
        )
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


async def generate_june_dispatch_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    year = int(filters.get("year") or date.today().year)
    month = int(filters.get("month") or 6)
    rows = []
    due_count = 0
    pending_count = 0
    completed_count = 0
    shortage_count = 0
    for po in await access.list_pos():
        if po.promise_delivery_date.year != year or po.promise_delivery_date.month != month:
            continue
        due_count += 1
        dispatch_stage = next((stage for stage in po.stage_summaries if stage.stage.value == "dispatch"), None)
        completed_qty = int(dispatch_stage.completed_qty or 0) if dispatch_stage else 0
        if po.status == POStatus.completed:
            completed_qty = max(completed_qty, po.order_quantity_pcs)
        pending_qty = max(po.order_quantity_pcs - completed_qty, 0)
        if pending_qty > 0:
            pending_count += 1
        if po.status == POStatus.completed:
            completed_count += 1
        shortage_m = float(po.fabric_plan.shortage_m) if po.fabric_plan and po.fabric_plan.shortage_m else 0.0
        if shortage_m > 0 and po.status != POStatus.completed:
            shortage_count += 1
        bottleneck = next((stage for stage in po.stage_summaries if stage.pending_qty > 0 and stage.stage.value != "dispatch"), None)
        rows.append(
            {
                "po_number": po.po_number,
                "product": po.product.product_name if po.product else "Product",
                "status": po.status.value,
                "order_qty": po.order_quantity_pcs,
                "completed_qty": completed_qty,
                "pending_qty": pending_qty,
                "fabric_shortage_m": round(shortage_m, 3),
                "bottleneck": bottleneck.stage.value if bottleneck else "-",
                "deadline": format_date(po.promise_delivery_date),
            }
        )
    return ReportPayload(
        title=f"{date(year, month, 1).strftime('%B %Y')} Dispatch Report",
        summary={
            "due_pos": due_count,
            "completed_pos": completed_count,
            "pending_pos": pending_count,
            "fabric_shortage_pos": shortage_count,
        },
        rows=rows,
        recommendations=["Clear shortage POs first, then move fabric-ready POs through cutting and packing."],
    )
