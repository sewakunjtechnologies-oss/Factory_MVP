from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import FabricPlanStatus, StageName
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageProgressEntry, StageSummary
from app.schemas.dashboard import BottleneckRead, DashboardPORead, OwnerDashboardRead
from app.services.alert_engine import list_alerts
from app.services.dispatch_engine import get_shipped_quantity
from app.services.operational_backfill import ensure_all_operational_data
from app.services.reminder_service import list_due_reminders


async def get_owner_dashboard(db: AsyncSession) -> OwnerDashboardRead:
    await ensure_all_operational_data(db)
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    rows: list[DashboardPORead] = []
    today = date.today()
    for po in result.scalars().all():
        shipped_qty = await get_shipped_quantity(db, po.id)
        completed_qty = _completed_or_dispatched_qty(po, shipped_qty)
        pending_qty = max(po.order_quantity_pcs - completed_qty, 0)
        bottleneck = _find_bottleneck(po.stage_summaries)
        shipment_risk = pending_qty > 0 and (po.promise_delivery_date - today).days <= 2
        fabric_shortage_m = float(po.fabric_plan.shortage_m) if po.fabric_plan and po.fabric_plan.status == FabricPlanStatus.shortage else 0.0
        rows.append(
            DashboardPORead(
                purchase_order_id=po.id,
                po_number=po.po_number,
                product=po.product.product_name if po.product else "Product",
                status=po.status.value,
                order_quantity_pcs=po.order_quantity_pcs,
                completed_qty=completed_qty,
                pending_qty=pending_qty,
                bottleneck_stage=bottleneck.stage if bottleneck else None,
                shipment_risk=shipment_risk,
                next_urgent_action=_next_action(po, bottleneck, shipment_risk, fabric_shortage_m, pending_qty),
                fabric_shortage_m=fabric_shortage_m,
            )
        )
    alerts = await list_alerts(db, active_only=True)
    reminders = await list_due_reminders(db)
    completed_today = await _completed_today(db, today)
    return OwnerDashboardRead(
        purchase_orders=rows,
        alerts=alerts,
        reminders=reminders,
        active_pos=sum(1 for row in rows if row.status not in {"completed", "cancelled"}),
        delayed_pos=sum(1 for row in rows if row.status == "delayed") + sum(1 for alert in alerts if alert.alert_type.value in {"stage_delay", "contractor_delay"}),
        fabric_shortages=sum(1 for row in rows if row.fabric_shortage_m > 0),
        shipment_risks=sum(1 for row in rows if row.shipment_risk),
        pending_dispatch=sum(1 for row in rows if row.pending_qty > 0 and row.status in {"dispatch", "partially_dispatched"}),
        completed_today=completed_today,
        top_bottleneck_stages=_top_bottlenecks(rows),
        action_cards=_action_cards(rows, alerts, reminders),
    )


def _completed_or_dispatched_qty(po: PurchaseOrder, shipped_qty: int) -> int:
    dispatch_stage = next((stage for stage in po.stage_summaries if stage.stage == StageName.dispatch), None)
    stage_completed = int(dispatch_stage.completed_qty or 0) if dispatch_stage else 0
    if po.status.value == "completed":
        return max(int(po.order_quantity_pcs), shipped_qty, stage_completed)
    return max(shipped_qty, stage_completed)


def _find_bottleneck(stages: list[StageSummary]) -> StageSummary | None:
    active_stages = [stage for stage in stages if stage.stage != StageName.dispatch and stage.pending_qty > 0]
    if not active_stages:
        return None
    return max(active_stages, key=lambda stage: stage.pending_qty)


def _next_action(po: PurchaseOrder, bottleneck: StageSummary | None, shipment_risk: bool, fabric_shortage_m: float, pending_qty: int) -> str:
    if fabric_shortage_m > 0:
        return "Act on fabric shortage"
    if shipment_risk and pending_qty > 0:
        return "Protect shipment date"
    if bottleneck is not None:
        return f"Push {bottleneck.stage.value.replace('_', ' ')}"
    if po.status.value in {"dispatch", "partially_dispatched"} and pending_qty > 0:
        return "Plan next dispatch load"
    return "Monitor execution"


def _top_bottlenecks(rows: list[DashboardPORead]) -> list[BottleneckRead]:
    totals: dict[StageName, dict[str, int]] = {}
    for row in rows:
        if row.bottleneck_stage is None:
            continue
        bucket = totals.setdefault(row.bottleneck_stage, {"pending_qty": 0, "po_count": 0})
        bucket["pending_qty"] += row.pending_qty
        bucket["po_count"] += 1
    return [
        BottleneckRead(stage=stage, pending_qty=values["pending_qty"], po_count=values["po_count"])
        for stage, values in sorted(totals.items(), key=lambda item: item[1]["pending_qty"], reverse=True)[:5]
    ]


async def _completed_today(db: AsyncSession, today: date) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(StageProgressEntry.approved_today), 0)).where(StageProgressEntry.entry_date == today)
    )
    return int(result.scalar_one())


def _action_cards(rows: list[DashboardPORead], alerts: list[object], reminders: list[object]) -> list[dict]:
    def _value(obj: object, attr: str) -> str:
        enum_obj = getattr(obj, attr, None)
        return getattr(enum_obj, "value", "")

    cards: list[dict] = []
    cards.append({"type": "fabric_not_ordered", "count": sum(1 for r in reminders if _value(r, "reminder_type") == "fabric_not_ordered"), "label": "Fabric Not Ordered"})
    cards.append({"type": "mill_delivery_overdue", "count": sum(1 for r in reminders if _value(r, "reminder_type") == "mill_delivery_overdue"), "label": "Mill Delivery Overdue"})
    cards.append({"type": "fabric_verification_pending", "count": sum(1 for r in reminders if _value(r, "reminder_type") == "fabric_verification_pending"), "label": "Fabric Verification Pending"})
    cards.append({"type": "cutting_wastage_high", "count": sum(1 for a in alerts if _value(a, "alert_type") == "high_cutting_wastage"), "label": "Cutting Wastage High"})
    cards.append({"type": "stitching_short", "count": sum(1 for r in reminders if _value(r, "reminder_type") == "stitching_output_short"), "label": "Stitching Short"})
    cards.append({"type": "packing_risk", "count": sum(1 for a in alerts if _value(a, "alert_type") == "packing_risk"), "label": "Packing Risk"})
    cards.append({"type": "dispatch_due", "count": sum(1 for r in reminders if _value(r, "reminder_type") == "dispatch_due"), "label": "Dispatch Due"})
    cards.append({"type": "reminders_due", "count": len(reminders), "label": "Reminders Due"})
    return cards
