from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    AlertPriority,
    AlertType,
    FabricMillOrderStatus,
    FabricVerificationAction,
    FabricVerificationStatus,
    ReceiptStatus,
)
from app.models.fabric import (
    FabricIssueToCutting,
    FabricMillOrder,
    FabricReceipt,
    MillDeliveryLot,
    MillFollowUp,
    MillOrderSplit,
    MillOrderStatusHistory,
)
from app.models.mill_requirement import MillOrderRequirement
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import ReminderPriority, ReminderType
from app.models.user import User
from app.models.stage import CuttingAnalysis, MillWastageRecord
from app.schemas.fabric import (
    FabricIssueToCuttingCreate,
    FabricMillOrderCreate,
    FabricVerificationUpdate,
    MillDeliveryLotCreate,
    MillFollowUpCreate,
    MillOrderShiftCreate,
    MillOrderSplitCreate,
)
from app.schemas.stage import CuttingAnalysisCreate
from app.services.audit_service import log_audit_event
from app.services.alert_engine import _create_once
from app.services.exceptions import DomainError
from app.services.fabric_planning import build_or_refresh_fabric_plan
from app.services.notification_service import create_notification
from app.services.reminder_service import upsert_reminder
from app.services.user_service import get_or_create_owner


WASTAGE_ALERT_THRESHOLD_M = Decimal("25")


async def _next_mill_invoice_number(db: AsyncSession) -> str:
    """Auto-generate a stable mill-invoice number scoped to the calendar year."""
    year = date.today().year
    prefix = f"MILL-INV-{year}-"
    result = await db.execute(
        select(func.max(FabricMillOrder.invoice_number)).where(FabricMillOrder.invoice_number.like(f"{prefix}%"))
    )
    last = result.scalar_one_or_none()
    if last:
        try:
            seq = int(last.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


async def create_fabric_mill_order(db: AsyncSession, payload: FabricMillOrderCreate) -> FabricMillOrder:
    po = await db.get(PurchaseOrder, payload.purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    order = FabricMillOrder(**payload.model_dump())
    if not order.invoice_number:
        order.invoice_number = await _next_mill_invoice_number(db)
    db.add(order)
    await db.flush()
    await log_audit_event(
        db,
        action_type="mill_order_created",
        entity_type="fabric_mill_order",
        entity_id=str(order.id),
        purchase_order_id=order.purchase_order_id,
        performed_by=payload.responsible_user_id,
        role="manager_or_owner",
        new_value_json={"mill_name": order.mill_name, "ordered_meters": str(order.ordered_meters), "status": order.status.value},
    )
    await db.commit()
    await db.refresh(order)
    return order


async def list_fabric_mill_orders(db: AsyncSession, purchase_order_id: UUID | None = None) -> list[FabricMillOrder]:
    statement = select(FabricMillOrder).order_by(FabricMillOrder.committed_delivery_date, FabricMillOrder.created_at.desc())
    if purchase_order_id is not None:
        statement = statement.where(FabricMillOrder.purchase_order_id == purchase_order_id)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def list_late_mill_orders(db: AsyncSession, today: date | None = None) -> list[FabricMillOrder]:
    current_date = today or date.today()
    result = await db.execute(
        select(FabricMillOrder).where(
            FabricMillOrder.status.notin_([FabricMillOrderStatus.received, FabricMillOrderStatus.cancelled]),
            FabricMillOrder.committed_delivery_date < current_date,
        )
    )
    return list(result.scalars().all())


async def create_mill_followup(db: AsyncSession, payload: MillFollowUpCreate) -> MillFollowUp:
    order = await db.get(FabricMillOrder, payload.mill_order_id)
    if order is None:
        raise DomainError(status_code=404, detail="Mill order not found")
    followup = MillFollowUp(**payload.model_dump())
    db.add(followup)
    order.status = payload.status
    await log_audit_event(
        db,
        action_type="mill_followup_recorded",
        entity_type="mill_followup",
        entity_id=str(followup.id),
        purchase_order_id=order.purchase_order_id,
        performed_by=payload.followup_by,
        role="mill_followup_user",
        new_value_json={"status": payload.status.value, "next_followup_date": payload.next_followup_date.isoformat() if payload.next_followup_date else None},
    )
    await db.commit()
    await db.refresh(followup)
    return followup


async def list_mill_followups_due(db: AsyncSession, on_date: date | None = None) -> list[MillFollowUp]:
    today = on_date or date.today()
    result = await db.execute(
        select(MillFollowUp)
        .where(
            MillFollowUp.next_followup_date.is_not(None),
            MillFollowUp.next_followup_date <= today,
        )
        .order_by(MillFollowUp.next_followup_date, MillFollowUp.created_at.desc())
    )
    return list(result.scalars().all())


async def verify_fabric_receipt(db: AsyncSession, payload: FabricVerificationUpdate) -> FabricReceipt:
    receipt = await db.get(FabricReceipt, payload.receipt_id)
    if receipt is None:
        raise DomainError(status_code=404, detail="Fabric receipt not found")

    receipt.verification_status = payload.verification_status
    receipt.action_taken = payload.action_taken
    receipt.verified_by = payload.verified_by
    receipt.verification_date = payload.verification_date
    receipt.mismatch_reason = payload.mismatch_reason
    receipt.remarks = payload.remarks

    if payload.verification_status in {FabricVerificationStatus.rejected, FabricVerificationStatus.returned, FabricVerificationStatus.mismatch}:
        receipt.status = ReceiptStatus.failed
        if receipt.purchase_order_id is not None:
            po = await db.get(PurchaseOrder, receipt.purchase_order_id)
            if po is not None:
                await db.refresh(po, attribute_names=["product", "fabric_plan"])
                await build_or_refresh_fabric_plan(db, po)
    elif payload.verification_status == FabricVerificationStatus.approved:
        receipt.status = ReceiptStatus.approved

    owner = await get_or_create_owner(db)
    await create_notification(
        db,
        user_id=owner.id,
        purchase_order_id=receipt.purchase_order_id,
        notification_type="fabric_verification_updated",
        title="Fabric verification updated",
        message=f"Receipt {receipt.id} is {payload.verification_status.value}.",
    )
    await log_audit_event(
        db,
        action_type="fabric_verified",
        entity_type="fabric_receipt",
        entity_id=str(receipt.id),
        purchase_order_id=receipt.purchase_order_id,
        performed_by=payload.verified_by,
        role="fabric_verifier",
        new_value_json={
            "verification_status": payload.verification_status.value,
            "action_taken": payload.action_taken.value,
            "verification_date": payload.verification_date.isoformat(),
            "mismatch_reason": payload.mismatch_reason,
        },
    )

    await db.commit()
    await db.refresh(receipt)
    return receipt


async def issue_fabric_to_cutting(db: AsyncSession, payload: FabricIssueToCuttingCreate) -> FabricIssueToCutting:
    if payload.fabric_receipt_id is None and payload.fabric_inventory_id is None:
        raise DomainError(status_code=400, detail="fabric_receipt_id or fabric_inventory_id is required")
    if payload.issued_meters <= 0:
        raise DomainError(status_code=400, detail="issued_meters must be greater than zero")

    if payload.fabric_receipt_id is not None:
        receipt = await db.get(FabricReceipt, payload.fabric_receipt_id)
        if receipt is None:
            raise DomainError(status_code=404, detail="Fabric receipt not found")
        if receipt.verification_status != FabricVerificationStatus.approved:
            raise DomainError(status_code=400, detail="Fabric can be issued only after verification approval")
        approved_meters = receipt.received_meters or receipt.received_length_m
        used_result = await db.execute(
            select(func.coalesce(func.sum(FabricIssueToCutting.issued_meters), 0)).where(
                FabricIssueToCutting.fabric_receipt_id == payload.fabric_receipt_id
            )
        )
        already_issued = Decimal(used_result.scalar_one() or 0)
        available = Decimal(approved_meters) - already_issued
        if payload.issued_meters > available:
            raise DomainError(status_code=400, detail="issued_meters cannot exceed verified available meters")

    issue = FabricIssueToCutting(**payload.model_dump())
    db.add(issue)
    if payload.contractor_id is not None and payload.expected_return_date is None:
        raise DomainError(status_code=400, detail="expected_return_date is required when contractor_id is set")
    if payload.expected_return_date is not None:
        await upsert_reminder(
            db,
            purchase_order_id=payload.purchase_order_id,
            reminder_type=ReminderType.cutting_due,
            title="Cutting return due",
            message=f"Cutting return expected by {payload.expected_return_date.isoformat()}",
            due_date=payload.expected_return_date,
            priority=ReminderPriority.medium,
            assigned_to=payload.received_by,
        )
    await db.flush()
    await log_audit_event(
        db,
        action_type="fabric_allocated_to_cutting",
        entity_type="fabric_issue_to_cutting",
        entity_id=str(issue.id),
        purchase_order_id=issue.purchase_order_id,
        performed_by=payload.issued_by,
        role="fabric_allocator",
        new_value_json={"issued_meters": str(issue.issued_meters), "issue_date": issue.issue_date.isoformat()},
    )
    await db.commit()
    await db.refresh(issue)
    return issue


async def list_fabric_issues(db: AsyncSession, purchase_order_id: UUID | None = None) -> list[FabricIssueToCutting]:
    statement = select(FabricIssueToCutting).order_by(FabricIssueToCutting.issue_date.desc(), FabricIssueToCutting.created_at.desc())
    if purchase_order_id is not None:
        statement = statement.where(FabricIssueToCutting.purchase_order_id == purchase_order_id)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def upsert_cutting_analysis(db: AsyncSession, payload: CuttingAnalysisCreate) -> CuttingAnalysis:
    if payload.actual_wastage_m < 0:
        raise DomainError(status_code=400, detail="actual_wastage_m cannot be negative")
    result = await db.execute(
        select(CuttingAnalysis).where(CuttingAnalysis.purchase_order_id == payload.purchase_order_id)
    )
    analysis = result.scalar_one_or_none()
    values = payload.model_dump()
    mill_name = values.pop("mill_name", None)
    difference = payload.actual_wastage_m - payload.planned_wastage_m
    if analysis is None:
        analysis = CuttingAnalysis(
            **values,
            wastage_difference_m=difference,
        )
        db.add(analysis)
    else:
        for key, value in values.items():
            setattr(analysis, key, value)
        analysis.wastage_difference_m = difference

    await db.flush()

    if mill_name:
        if difference > WASTAGE_ALERT_THRESHOLD_M:
            flag = "high"
        elif difference < -WASTAGE_ALERT_THRESHOLD_M:
            flag = "low"
        else:
            flag = "normal"
        db.add(
            MillWastageRecord(
                purchase_order_id=payload.purchase_order_id,
                mill_name=mill_name.strip(),
                cutting_analysis_id=analysis.id,
                planned_wastage_m=payload.planned_wastage_m,
                actual_wastage_m=payload.actual_wastage_m,
                wastage_difference_m=difference,
                flag=flag,
                recorded_by=payload.cutting_supervisor_id,
            )
        )

    if difference > WASTAGE_ALERT_THRESHOLD_M:
        await _create_once(
            db,
            payload.purchase_order_id,
            AlertType.high_cutting_wastage,
            AlertPriority.high,
            "Cutting wastage high",
            f"Actual wastage exceeds plan by {difference}m.",
        )
        owner = await get_or_create_owner(db)
        await create_notification(
            db,
            user_id=owner.id,
            purchase_order_id=payload.purchase_order_id,
            notification_type="high_wastage",
            title="High cutting wastage",
            message=f"PO {payload.purchase_order_id}: wastage exceeds plan by {difference}m.",
        )
    await log_audit_event(
        db,
        action_type="cutting_wastage_verified",
        entity_type="cutting_analysis",
        entity_id=str(analysis.id),
        purchase_order_id=payload.purchase_order_id,
        performed_by=payload.cutting_supervisor_id,
        role="cutting_verifier",
        new_value_json={
            "planned_wastage_m": str(payload.planned_wastage_m),
            "actual_wastage_m": str(payload.actual_wastage_m),
            "wastage_difference_m": str(difference),
        },
    )
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def list_cutting_analysis(db: AsyncSession, purchase_order_id: UUID | None = None) -> list[CuttingAnalysis]:
    statement = select(CuttingAnalysis).order_by(CuttingAnalysis.updated_at.desc())
    if purchase_order_id is not None:
        statement = statement.where(CuttingAnalysis.purchase_order_id == purchase_order_id)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def list_mill_wastage_records(
    db: AsyncSession, mill_name: str | None = None, purchase_order_id: UUID | None = None
) -> list[MillWastageRecord]:
    statement = select(MillWastageRecord).order_by(MillWastageRecord.recorded_at.desc())
    if mill_name is not None:
        statement = statement.where(MillWastageRecord.mill_name == mill_name)
    if purchase_order_id is not None:
        statement = statement.where(MillWastageRecord.purchase_order_id == purchase_order_id)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def get_mill_wastage_history(db: AsyncSession) -> list[dict]:
    """Aggregate wastage events per mill so the owner can see which mills are risky.

    Returned `flag` reflects the average wastage_difference_m:
      - high  → averaged above +25m (mill consistently exceeds plan)
      - low   → averaged below -25m (mill consistently under plan / efficient)
      - normal → within ±25m
    """
    threshold = WASTAGE_ALERT_THRESHOLD_M
    statement = (
        select(
            MillWastageRecord.mill_name,
            func.count(MillWastageRecord.id).label("event_count"),
            func.coalesce(func.sum(MillWastageRecord.planned_wastage_m), 0).label("total_planned_wastage_m"),
            func.coalesce(func.sum(MillWastageRecord.actual_wastage_m), 0).label("total_actual_wastage_m"),
            func.coalesce(func.sum(MillWastageRecord.wastage_difference_m), 0).label("total_difference_m"),
            func.coalesce(func.avg(MillWastageRecord.wastage_difference_m), 0).label("avg_difference_m"),
            func.max(MillWastageRecord.recorded_at).label("last_recorded_at"),
        )
        .group_by(MillWastageRecord.mill_name)
        .order_by(func.coalesce(func.avg(MillWastageRecord.wastage_difference_m), 0).desc())
    )
    rows = (await db.execute(statement)).all()
    history: list[dict] = []
    for row in rows:
        avg = Decimal(row.avg_difference_m or 0)
        if avg > threshold:
            flag = "high"
        elif avg < -threshold:
            flag = "low"
        else:
            flag = "normal"
        history.append(
            {
                "mill_name": row.mill_name,
                "event_count": int(row.event_count or 0),
                "total_planned_wastage_m": Decimal(row.total_planned_wastage_m or 0),
                "total_actual_wastage_m": Decimal(row.total_actual_wastage_m or 0),
                "total_difference_m": Decimal(row.total_difference_m or 0),
                "avg_difference_m": avg,
                "last_recorded_at": row.last_recorded_at,
                "flag": flag,
            }
        )
    return history


async def generate_fabric_followup_reminders(db: AsyncSession, today: date | None = None) -> None:
    current_date = today or date.today()
    # PO without mill orders
    po_result = await db.execute(select(PurchaseOrder))
    pos = list(po_result.scalars().all())
    for po in pos:
        has_order_result = await db.execute(
            select(FabricMillOrder.id).where(
                and_(
                    FabricMillOrder.purchase_order_id == po.id,
                    FabricMillOrder.status != FabricMillOrderStatus.cancelled,
                )
            )
        )
        has_order = has_order_result.first() is not None
        if not has_order:
            await upsert_reminder(
                db,
                purchase_order_id=po.id,
                reminder_type=ReminderType.fabric_not_ordered,
                title="Fabric not ordered",
                message=f"PO {po.po_number} has no active mill order.",
                due_date=current_date,
                priority=ReminderPriority.high,
            )

    # due and overdue mill orders
    mill_orders = await list_fabric_mill_orders(db)
    for order in mill_orders:
        if order.status in {FabricMillOrderStatus.received, FabricMillOrderStatus.cancelled}:
            continue
        if order.committed_delivery_date < current_date:
            reminder_type = ReminderType.mill_delivery_overdue
            title = "Mill delivery overdue"
            priority = ReminderPriority.high
            owner = await get_or_create_owner(db)
            # Auto-transition still-open orders past their committed date into the `delayed` state
            # so dashboards and the AI assistant treat them as late without manual flips.
            if order.status == FabricMillOrderStatus.ordered:
                previous_status = order.status
                order.status = FabricMillOrderStatus.delayed
                db.add(
                    MillOrderStatusHistory(
                        fabric_mill_order_id=order.id,
                        previous_status=previous_status,
                        new_status=FabricMillOrderStatus.delayed,
                        reason="Auto-transition: committed_delivery_date passed without delivery.",
                    )
                )
            await create_notification(
                db,
                user_id=owner.id,
                purchase_order_id=order.purchase_order_id,
                notification_type="mill_delivery_overdue",
                title="Mill delivery overdue",
                message=f"{order.mill_name} is overdue for PO {order.purchase_order_id}.",
            )
        elif order.committed_delivery_date == current_date:
            reminder_type = ReminderType.mill_delivery_due_today
            title = "Mill delivery due today"
            priority = ReminderPriority.high
        elif (order.committed_delivery_date - current_date).days == 1:
            reminder_type = ReminderType.mill_delivery_due_tomorrow
            title = "Mill delivery due tomorrow"
            priority = ReminderPriority.medium
        else:
            reminder_type = ReminderType.mill_delivery_due
            title = "Mill delivery due"
            priority = ReminderPriority.medium
        await upsert_reminder(
            db,
            purchase_order_id=order.purchase_order_id,
            reminder_type=reminder_type,
            title=title,
            message=f"{order.mill_name} delivery committed for {order.committed_delivery_date.isoformat()}.",
            due_date=order.committed_delivery_date,
            priority=priority,
            assigned_to=order.responsible_user_id,
        )


async def create_mill_order_split(db: AsyncSession, payload: MillOrderSplitCreate, actor_id: UUID | None = None) -> list[MillOrderSplit]:
    po = await db.get(PurchaseOrder, payload.purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    requirement: MillOrderRequirement | None = None
    if payload.mill_order_requirement_id:
        requirement = await db.get(MillOrderRequirement, payload.mill_order_requirement_id)
    shortage_meters = Decimal(requirement.shortage_meters if requirement else (po.fabric_plan.shortage_m if po.fabric_plan else 0))
    if shortage_meters <= 0:
        raise DomainError(status_code=400, detail="No shortage meters available for mill split")

    created: list[MillOrderSplit] = []
    for split in payload.splits:
        ordered_meters = (shortage_meters * split.split_percent / Decimal("100")).quantize(Decimal("0.001"))
        split_row = MillOrderSplit(
            purchase_order_id=payload.purchase_order_id,
            mill_order_requirement_id=payload.mill_order_requirement_id,
            mill_name=split.mill_name,
            split_percent=split.split_percent,
            ordered_meters=ordered_meters,
            committed_delivery_date=split.committed_delivery_date,
            responsible_user_id=split.responsible_user_id,
        )
        db.add(split_row)
        created.append(split_row)
        db.add(
            FabricMillOrder(
                purchase_order_id=payload.purchase_order_id,
                mill_name=split.mill_name,
                invoice_number=await _next_mill_invoice_number(db),
                ordered_meters=ordered_meters,
                ordered_width=split.ordered_width,
                ordered_gsm=split.ordered_gsm,
                ordered_rate_per_meter=split.ordered_rate_per_meter,
                committed_delivery_date=split.committed_delivery_date,
                responsible_user_id=split.responsible_user_id,
                status=FabricMillOrderStatus.ordered,
            )
        )
        # Flush so the next iteration's _next_mill_invoice_number sees the row we just added.
        await db.flush()
        await upsert_reminder(
            db,
            purchase_order_id=payload.purchase_order_id,
            reminder_type=ReminderType.mill_delivery_due,
            title="Mill delivery due",
            message=f"{split.mill_name} delivery due on {split.committed_delivery_date.isoformat()}",
            due_date=split.committed_delivery_date,
            priority=ReminderPriority.medium,
            assigned_to=split.responsible_user_id,
        )
    await db.flush()
    await log_audit_event(
        db,
        action_type="mill_split_created",
        entity_type="mill_order_split",
        entity_id=str(payload.purchase_order_id),
        purchase_order_id=payload.purchase_order_id,
        performed_by=actor_id,
        role="manager_or_owner",
        new_value_json={"splits": [{"mill_name": item.mill_name, "split_percent": str(item.split_percent)} for item in payload.splits]},
    )
    await db.commit()
    for item in created:
        await db.refresh(item)
    return created


async def list_mill_order_splits(db: AsyncSession, purchase_order_id: UUID | None = None) -> list[MillOrderSplit]:
    statement = select(MillOrderSplit).order_by(MillOrderSplit.created_at.desc())
    if purchase_order_id is not None:
        statement = statement.where(MillOrderSplit.purchase_order_id == purchase_order_id)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def record_mill_delivery_lot(db: AsyncSession, payload: MillDeliveryLotCreate, actor_id: UUID | None = None) -> MillDeliveryLot:
    order = await db.get(FabricMillOrder, payload.fabric_mill_order_id)
    if order is None:
        raise DomainError(status_code=404, detail="Mill order not found")
    if payload.delivered_meters > order.ordered_meters:
        raise DomainError(status_code=400, detail="delivered_meters cannot exceed ordered_meters")
    lot = MillDeliveryLot(
        fabric_mill_order_id=payload.fabric_mill_order_id,
        lot_number=payload.lot_number,
        delivered_meters=payload.delivered_meters,
        received_date=payload.received_date,
        quality_notes=payload.quality_notes,
    )
    db.add(lot)
    existing_result = await db.execute(
        select(func.coalesce(func.sum(MillDeliveryLot.delivered_meters), 0)).where(MillDeliveryLot.fabric_mill_order_id == order.id)
    )
    delivered_total = Decimal(existing_result.scalar_one() or 0) + payload.delivered_meters
    previous_status = order.status
    if delivered_total >= order.ordered_meters:
        order.status = FabricMillOrderStatus.received
        order.actual_delivery_date = payload.received_date
    else:
        order.status = FabricMillOrderStatus.partially_received
        await upsert_reminder(
            db,
            purchase_order_id=order.purchase_order_id,
            reminder_type=ReminderType.followup_due,
            title="Partial delivery pending",
            message=f"{order.mill_name} delivered partial quantity for order {order.id}.",
            due_date=payload.received_date,
            priority=ReminderPriority.high,
            assigned_to=order.responsible_user_id,
        )
    db.add(
        MillOrderStatusHistory(
            fabric_mill_order_id=order.id,
            previous_status=previous_status,
            new_status=order.status,
            reason="Mill delivery lot received",
            changed_by=actor_id,
        )
    )
    await log_audit_event(
        db,
        action_type="partial_mill_delivery_received" if order.status == FabricMillOrderStatus.partially_received else "mill_delivery_received",
        entity_type="mill_delivery_lot",
        entity_id=str(lot.id),
        purchase_order_id=order.purchase_order_id,
        performed_by=actor_id,
        role="manager_or_mill_followup_user",
        new_value_json={"lot_number": lot.lot_number, "delivered_meters": str(lot.delivered_meters), "status": order.status.value},
    )
    await db.commit()
    await db.refresh(lot)
    return lot


async def list_mill_delivery_lots(db: AsyncSession, mill_order_id: UUID | None = None) -> list[MillDeliveryLot]:
    statement = select(MillDeliveryLot).order_by(MillDeliveryLot.received_date.desc(), MillDeliveryLot.created_at.desc())
    if mill_order_id is not None:
        statement = statement.where(MillDeliveryLot.fabric_mill_order_id == mill_order_id)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def cancel_mill_order(
    db: AsyncSession,
    mill_order_id: UUID,
    *,
    reason: str,
    actor_id: UUID | None,
) -> FabricMillOrder:
    order = await db.get(FabricMillOrder, mill_order_id)
    if order is None:
        raise DomainError(status_code=404, detail="Mill order not found")
    previous_status = order.status
    order.status = FabricMillOrderStatus.cancelled
    db.add(
        MillOrderStatusHistory(
            fabric_mill_order_id=order.id,
            previous_status=previous_status,
            new_status=FabricMillOrderStatus.cancelled,
            reason=reason,
            changed_by=actor_id,
        )
    )
    await log_audit_event(
        db,
        action_type="mill_order_cancelled",
        entity_type="fabric_mill_order",
        entity_id=str(order.id),
        purchase_order_id=order.purchase_order_id,
        performed_by=actor_id,
        role="manager_or_owner",
        old_value_json={"status": previous_status.value},
        new_value_json={"status": "cancelled", "reason": reason},
    )
    await db.commit()
    await db.refresh(order)
    return order


async def shift_mill_order_quantity(db: AsyncSession, payload: MillOrderShiftCreate, actor_id: UUID | None = None) -> FabricMillOrder:
    from_order = await db.get(FabricMillOrder, payload.from_mill_order_id)
    if from_order is None:
        raise DomainError(status_code=404, detail="Source mill order not found")
    delivered_result = await db.execute(
        select(func.coalesce(func.sum(MillDeliveryLot.delivered_meters), 0)).where(MillDeliveryLot.fabric_mill_order_id == from_order.id)
    )
    delivered_meters = Decimal(delivered_result.scalar_one() or 0)
    available_to_shift = from_order.ordered_meters - delivered_meters
    if payload.shift_meters > available_to_shift:
        raise DomainError(status_code=400, detail="shift_meters cannot exceed pending mill quantity")
    from_order.ordered_meters = (from_order.ordered_meters - payload.shift_meters).quantize(Decimal("0.001"))
    replacement = FabricMillOrder(
        purchase_order_id=from_order.purchase_order_id,
        mill_name=payload.to_mill_name,
        ordered_meters=payload.shift_meters,
        ordered_width=from_order.ordered_width,
        ordered_gsm=from_order.ordered_gsm,
        ordered_rate_per_meter=from_order.ordered_rate_per_meter,
        committed_delivery_date=payload.committed_delivery_date,
        responsible_user_id=payload.responsible_user_id,
        status=FabricMillOrderStatus.replacement_required,
    )
    db.add(replacement)
    await db.flush()
    await log_audit_event(
        db,
        action_type="mill_quantity_shifted",
        entity_type="fabric_mill_order",
        entity_id=str(from_order.id),
        purchase_order_id=from_order.purchase_order_id,
        performed_by=actor_id,
        role="manager_or_owner",
        new_value_json={
            "shift_meters": str(payload.shift_meters),
            "to_mill_name": payload.to_mill_name,
            "replacement_order_id": str(replacement.id),
            "reason": payload.reason,
        },
    )
    await db.commit()
    await db.refresh(replacement)
    return replacement
