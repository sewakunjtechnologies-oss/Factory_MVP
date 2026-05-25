from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alert import Alert
from app.models.enums import AlertPriority, AlertType, FabricPlanStatus, StageName
from app.models.purchase_order import PurchaseOrder
from app.models.stage import ContractorAllocation, StageSummary
from app.services.dispatch_engine import get_shipped_quantity
from app.services.exceptions import DomainError
from app.services.packing_engine import analyze_packing


async def list_alerts(db: AsyncSession, active_only: bool = True) -> list[Alert]:
    statement = select(Alert).order_by(Alert.created_at.desc())
    if active_only:
        statement = statement.where(Alert.is_resolved.is_(False))
    result = await db.execute(statement)
    return list(result.scalars().all())


async def resolve_alert(db: AsyncSession, alert_id: UUID) -> Alert:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise DomainError(status_code=404, detail="Alert not found")
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alert)
    return alert


async def generate_alerts(db: AsyncSession) -> list[Alert]:
    today = date.today()
    result = await db.execute(
        select(PurchaseOrder).options(
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
        )
    )
    purchase_orders = list(result.scalars().all())
    generated: list[Alert] = []
    for po in purchase_orders:
        if po.fabric_plan and po.fabric_plan.status == FabricPlanStatus.shortage:
            generated.append(
                await _create_once(
                    db,
                    po.id,
                    AlertType.stock_shortage,
                    AlertPriority.critical,
                    "Fabric shortage",
                    f"PO {po.po_number} has {po.fabric_plan.shortage_m}m fabric shortage.",
                )
            )

        shipped_qty = await get_shipped_quantity(db, po.id)
        pending_qty = max(po.order_quantity_pcs - shipped_qty, 0)
        days_left = (po.promise_delivery_date - today).days
        if pending_qty > 0 and days_left <= 2:
            generated.append(
                await _create_once(
                    db,
                    po.id,
                    AlertType.shipment_risk,
                    AlertPriority.high if days_left >= 0 else AlertPriority.critical,
                    "Shipment risk",
                    f"PO {po.po_number} has {pending_qty} pcs pending with {max(days_left, 0)} days left.",
                )
            )

        for stage in po.stage_summaries:
            if stage.input_qty > 0 and stage.pending_qty > 0 and days_left < 0:
                generated.append(
                    await _create_once(
                        db,
                        po.id,
                        AlertType.stage_delay,
                        AlertPriority.high,
                        "Stage delay",
                        f"PO {po.po_number} is delayed at {stage.stage.value}.",
                    )
                )
            if stage.input_qty > 0 and stage.rejected_qty / stage.input_qty > 0.05:
                generated.append(
                    await _create_once(
                        db,
                        po.id,
                        AlertType.high_rejection,
                        AlertPriority.high,
                        "High rejection",
                        f"PO {po.po_number} has high rejection at {stage.stage.value}.",
                    )
                )
            if stage.stage == StageName.packing and stage.pending_qty > 0 and days_left <= 2:
                packing = await analyze_packing(db, po.id, avg_per_packer=100, actual_packers=1, as_of=today)
                if not packing.packing_risk:
                    continue
                generated.append(
                    await _create_once(
                        db,
                        po.id,
                        AlertType.packing_risk,
                        AlertPriority.high,
                        "Packing risk",
                        f"PO {po.po_number} needs {packing.required_packers} packers for {packing.remaining_qty} pcs with {packing.days_left} days left.",
                    )
                )

    generated.extend(await _generate_contractor_delay_alerts(db, today))
    await db.commit()
    return [alert for alert in generated if alert is not None]


async def _generate_contractor_delay_alerts(db: AsyncSession, today: date) -> list[Alert]:
    result = await db.execute(
        select(ContractorAllocation)
        .where(
            ContractorAllocation.expected_completion_date.is_not(None),
            ContractorAllocation.expected_completion_date < today,
            ContractorAllocation.completed_qty < ContractorAllocation.issued_qty,
        )
        .options(
            selectinload(ContractorAllocation.contractor),
            selectinload(ContractorAllocation.stage_summary),
        )
    )
    alerts: list[Alert] = []
    for allocation in result.scalars().all():
        po_id = allocation.stage_summary.purchase_order_id
        alerts.append(
            await _create_once(
                db,
                po_id,
                AlertType.contractor_delay,
                AlertPriority.medium,
                "Contractor delay",
                f"{allocation.contractor.name} is delayed on {allocation.stage_summary.stage.value}.",
            )
        )
    return alerts


async def _create_once(
    db: AsyncSession,
    purchase_order_id: UUID | None,
    alert_type: AlertType,
    priority: AlertPriority,
    title: str,
    message: str,
) -> Alert | None:
    existing = await db.execute(
        select(Alert).where(
            Alert.purchase_order_id == purchase_order_id,
            Alert.alert_type == alert_type,
            Alert.title == title,
            Alert.is_resolved.is_(False),
        )
    )
    if existing.scalar_one_or_none() is not None:
        return None
    alert = Alert(
        purchase_order_id=purchase_order_id,
        alert_type=alert_type,
        priority=priority,
        title=title,
        message=message,
    )
    db.add(alert)
    return alert
