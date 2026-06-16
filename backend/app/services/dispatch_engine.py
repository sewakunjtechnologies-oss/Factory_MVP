from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispatch import DispatchLoad
from app.models.enums import DispatchCostType, POStatus, StageName, StageStatus
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageSummary
from app.schemas.dispatch import DispatchLoadCreate, DispatchLoadUpdate, DispatchSummaryRead
from app.services.audit_service import log_audit_event
from app.services.exceptions import DomainError
from app.services.notification_service import create_notification
from app.services.user_service import get_or_create_owner


async def create_dispatch_load(db: AsyncSession, payload: DispatchLoadCreate) -> DispatchLoad:
    po = await db.get(PurchaseOrder, payload.purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")

    packing_stage = await _get_stage(db, po.id, StageName.packing)
    dispatch_stage = await _get_stage(db, po.id, StageName.dispatch)
    shipped_so_far = await get_shipped_quantity(db, po.id)
    available_to_ship = packing_stage.approved_qty - shipped_so_far
    if payload.shipped_qty > available_to_ship:
        raise DomainError(status_code=400, detail="shipped_qty cannot exceed packed and approved quantity")
    if payload.shipped_qty <= 0:
        raise DomainError(status_code=400, detail="shipped_qty must be greater than zero")
    total_shipped = shipped_so_far + payload.shipped_qty

    dispatch_cost = calculate_dispatch_cost(payload)
    loaded_pieces = payload.actual_loaded_pieces or payload.shipped_qty
    if loaded_pieces <= 0:
        raise DomainError(status_code=400, detail="actual_loaded_pieces must be greater than zero")
    if loaded_pieces > available_to_ship:
        raise DomainError(status_code=400, detail="actual_loaded_pieces cannot exceed dispatch-ready quantity")
    cost_per_piece = (dispatch_cost / Decimal(loaded_pieces)).quantize(Decimal("0.0001"))
    if payload.cost_type == DispatchCostType.vehicle_capacity:
        cost_per_piece = dispatch_cost
    actual_cost_percent = None
    if payload.invoice_value and payload.invoice_value > 0:
        actual_cost_percent = (dispatch_cost / payload.invoice_value * Decimal("100")).quantize(Decimal("0.001"))
    load = DispatchLoad(
        purchase_order_id=payload.purchase_order_id,
        load_number=payload.load_number,
        shipped_qty=payload.shipped_qty,
        vehicle_type=payload.vehicle_type,
        vehicle_identifier=payload.vehicle_identifier,
        expected_piece_capacity=payload.expected_piece_capacity,
        actual_loaded_pieces=payload.actual_loaded_pieces,
        cbm_capacity=payload.cbm_capacity,
        cbm_used=payload.cbm_used,
        cost_type=payload.cost_type,
        invoice_value=payload.invoice_value,
        dispatch_percent=payload.dispatch_percent,
        cbm_value=payload.cbm_value,
        cbm_rate=payload.cbm_rate,
        manual_cost=payload.manual_cost,
        vehicle_cost=payload.vehicle_cost,
        dispatch_cost=dispatch_cost,
        cost_per_piece=cost_per_piece,
        expected_cost_percent=payload.dispatch_percent,
        actual_cost_percent=actual_cost_percent,
        shipped_at=payload.shipped_at,
        transporter_name=payload.transporter_name,
        destination=payload.destination,
        tracking_reference=payload.tracking_reference,
        document_status=payload.document_status or "complete",
        invoice_uploaded=payload.invoice_uploaded,
        packing_list_uploaded=payload.packing_list_uploaded,
        eway_bill_uploaded=payload.eway_bill_uploaded,
        transporter_confirmation=payload.transporter_confirmation,
        buyer_dispatch_approval=payload.buyer_dispatch_approval,
        shortfall_qty=max(po.order_quantity_pcs - total_shipped, 0),
        shortfall_reason=payload.shortfall_reason,
        linked_repair_qty=payload.linked_repair_qty,
        linked_alteration_qty=payload.linked_alteration_qty,
        assigned_to=payload.assigned_to,
        responsible_role=payload.responsible_role,
        completed_by=payload.completed_by,
        completed_at=payload.completed_at,
        remarks=payload.remarks,
    )
    db.add(load)

    await db.flush()
    await _sync_po_dispatch_state(db, po)
    await log_audit_event(
        db,
        action_type="dispatch_record_created",
        entity_type="dispatch_load",
        entity_id=str(load.id),
        purchase_order_id=po.id,
        performed_by=payload.completed_by or payload.assigned_to,
        role=payload.responsible_role or "dispatcher",
        new_value_json={
            "shipped_qty": payload.shipped_qty,
            "total_shipped": total_shipped,
            "shortfall_qty": max(po.order_quantity_pcs - total_shipped, 0),
            "document_status": load.document_status,
            "cost_type": load.cost_type.value,
        },
    )
    if total_shipped < po.order_quantity_pcs:
        owner = await get_or_create_owner(db)
        await create_notification(
            db,
            user_id=owner.id,
            purchase_order_id=po.id,
            notification_type="dispatch_shortfall",
            title="Dispatch shortfall",
            message=f"PO {po.po_number} dispatched {total_shipped}/{po.order_quantity_pcs}.",
        )

    await db.commit()
    await db.refresh(load)
    return load


async def update_dispatch_load(
    db: AsyncSession,
    dispatch_load_id: UUID,
    payload: DispatchLoadUpdate,
    *,
    updated_by: UUID | None = None,
    updated_role: str | None = None,
) -> DispatchLoad:
    load = await db.get(DispatchLoad, dispatch_load_id)
    if load is None:
        raise DomainError(status_code=404, detail="Dispatch load not found")
    old_values = _dispatch_load_snapshot(load)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(load, field, value)

    po = await _validate_and_reprice_load(db, load)
    await _sync_po_dispatch_state(db, po)
    await log_audit_event(
        db,
        action_type="dispatch_record_updated",
        entity_type="dispatch_load",
        entity_id=str(load.id),
        purchase_order_id=load.purchase_order_id,
        performed_by=updated_by,
        role=updated_role or "dispatcher",
        old_value_json=old_values,
        new_value_json=_dispatch_load_snapshot(load),
    )
    await db.commit()
    await db.refresh(load)
    return load


async def delete_dispatch_load(
    db: AsyncSession,
    dispatch_load_id: UUID,
    *,
    deleted_by: UUID | None = None,
    deleted_role: str | None = None,
) -> None:
    load = await db.get(DispatchLoad, dispatch_load_id)
    if load is None:
        raise DomainError(status_code=404, detail="Dispatch load not found")
    po_id = load.purchase_order_id
    snapshot = _dispatch_load_snapshot(load)
    await log_audit_event(
        db,
        action_type="dispatch_record_deleted",
        entity_type="dispatch_load",
        entity_id=str(load.id),
        purchase_order_id=po_id,
        performed_by=deleted_by,
        role=deleted_role or "dispatcher",
        old_value_json=snapshot,
    )
    await db.delete(load)
    await db.flush()
    po = await db.get(PurchaseOrder, po_id)
    if po is not None:
        await _sync_po_dispatch_state(db, po)
    await db.commit()


def calculate_dispatch_cost(payload: DispatchLoadCreate) -> Decimal:
    if payload.cost_type == DispatchCostType.invoice_percent:
        if payload.invoice_value is None or payload.dispatch_percent is None:
            raise DomainError(status_code=400, detail="invoice_value and dispatch_percent are required")
        return (payload.invoice_value * payload.dispatch_percent / Decimal("100")).quantize(Decimal("0.01"))
    if payload.cost_type == DispatchCostType.cbm:
        cbm_base = payload.cbm_used if payload.cbm_used is not None else payload.cbm_value
        if cbm_base is None or payload.cbm_rate is None:
            raise DomainError(status_code=400, detail="cbm_used/cbm_value and cbm_rate are required")
        return (cbm_base * payload.cbm_rate).quantize(Decimal("0.01"))
    if payload.cost_type == DispatchCostType.manual:
        if payload.manual_cost is None:
            raise DomainError(status_code=400, detail="manual_cost is required")
        return payload.manual_cost.quantize(Decimal("0.01"))
    if payload.cost_type == DispatchCostType.vehicle_capacity:
        if payload.vehicle_cost is None:
            raise DomainError(status_code=400, detail="vehicle_cost is required")
        loaded = payload.actual_loaded_pieces or payload.shipped_qty
        if loaded <= 0:
            raise DomainError(status_code=400, detail="actual_loaded_pieces must be greater than zero")
        return (payload.vehicle_cost / Decimal(loaded)).quantize(Decimal("0.01"))
    raise DomainError(status_code=400, detail="unsupported dispatch cost type")


async def list_dispatch_loads(db: AsyncSession, purchase_order_id: UUID) -> list[DispatchLoad]:
    result = await db.execute(
        select(DispatchLoad)
        .where(DispatchLoad.purchase_order_id == purchase_order_id)
        .order_by(DispatchLoad.shipped_at.desc(), DispatchLoad.created_at.desc())
    )
    return list(result.scalars().all())


async def get_dispatch_summary(db: AsyncSession, purchase_order_id: UUID) -> DispatchSummaryRead:
    po = await db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    loads = await list_dispatch_loads(db, purchase_order_id)
    total_dispatched = sum(load.shipped_qty for load in loads)
    total_cost = sum((load.dispatch_cost for load in loads), Decimal("0.00"))
    average = Decimal("0.0000") if total_dispatched == 0 else (total_cost / Decimal(total_dispatched)).quantize(Decimal("0.0001"))
    return DispatchSummaryRead(
        purchase_order_id=purchase_order_id,
        total_dispatched=total_dispatched,
        pending_dispatch=max(po.order_quantity_pcs - total_dispatched, 0),
        total_dispatch_cost=total_cost.quantize(Decimal("0.01")),
        average_cost_per_piece=average,
        loads=loads,
    )


async def _validate_and_reprice_load(db: AsyncSession, load: DispatchLoad) -> PurchaseOrder:
    po = await db.get(PurchaseOrder, load.purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    packing_stage = await _get_stage(db, po.id, StageName.packing)
    shipped_other = await get_shipped_quantity(db, po.id, exclude_load_id=load.id)
    available_to_this_load = packing_stage.approved_qty - shipped_other
    if load.document_status == "blocked" and load.shipped_qty > 0:
        raise DomainError(status_code=400, detail="Dispatch is blocked by missing documentation")
    if load.shipped_qty <= 0:
        raise DomainError(status_code=400, detail="shipped_qty must be greater than zero")
    if load.shipped_qty > available_to_this_load:
        raise DomainError(status_code=400, detail="shipped_qty cannot exceed packed and approved quantity")
    loaded_pieces = load.actual_loaded_pieces or load.shipped_qty
    if loaded_pieces <= 0:
        raise DomainError(status_code=400, detail="actual_loaded_pieces must be greater than zero")
    if loaded_pieces > available_to_this_load:
        raise DomainError(status_code=400, detail="actual_loaded_pieces cannot exceed dispatch-ready quantity")
    dispatch_cost = calculate_dispatch_cost(load)  # type: ignore[arg-type]
    cost_per_piece = (dispatch_cost / Decimal(loaded_pieces)).quantize(Decimal("0.0001"))
    if load.cost_type == DispatchCostType.vehicle_capacity:
        cost_per_piece = dispatch_cost
    actual_cost_percent = None
    if load.invoice_value and load.invoice_value > 0:
        actual_cost_percent = (dispatch_cost / load.invoice_value * Decimal("100")).quantize(Decimal("0.001"))
    load.dispatch_cost = dispatch_cost
    load.cost_per_piece = cost_per_piece
    load.expected_cost_percent = load.dispatch_percent
    load.actual_cost_percent = actual_cost_percent
    return po


async def _sync_po_dispatch_state(db: AsyncSession, po: PurchaseOrder) -> None:
    packing_stage = await _get_stage(db, po.id, StageName.packing)
    dispatch_stage = await _get_stage(db, po.id, StageName.dispatch)
    loads = await list_dispatch_loads(db, po.id)
    chronological_loads = sorted(loads, key=lambda load: (load.shipped_at, load.created_at))
    total_shipped = 0
    has_exception = False
    latest_ship_date = None
    for load in chronological_loads:
        total_shipped += load.shipped_qty
        has_exception = has_exception or load.linked_repair_qty > 0 or load.linked_alteration_qty > 0 or bool(load.shortfall_reason)
        latest_ship_date = load.shipped_at
        load.shortfall_qty = max(po.order_quantity_pcs - total_shipped, 0)

    dispatch_stage.input_qty = max(dispatch_stage.input_qty, packing_stage.approved_qty)
    if dispatch_stage.input_qty > packing_stage.approved_qty:
        dispatch_stage.input_qty = packing_stage.approved_qty
    dispatch_stage.completed_qty = total_shipped
    dispatch_stage.approved_qty = total_shipped
    dispatch_stage.pending_qty = max(dispatch_stage.input_qty - dispatch_stage.completed_qty, 0)
    if total_shipped >= po.order_quantity_pcs:
        dispatch_stage.status = StageStatus.completed
        po.status = POStatus.completed
        po.actual_delivery_date = latest_ship_date
    elif total_shipped > 0:
        dispatch_stage.status = StageStatus.in_progress
        po.status = POStatus.dispatched_with_exception if has_exception else POStatus.partially_dispatched
        po.actual_delivery_date = None
    else:
        dispatch_stage.status = StageStatus.not_started if dispatch_stage.input_qty == 0 else StageStatus.in_progress
        if po.status in {POStatus.partially_dispatched, POStatus.dispatched_with_exception, POStatus.completed}:
            po.status = POStatus.packing if packing_stage.approved_qty > 0 else POStatus.dispatch
        po.actual_delivery_date = None


def _dispatch_load_snapshot(load: DispatchLoad) -> dict:
    return {
        "load_number": load.load_number,
        "shipped_qty": load.shipped_qty,
        "vehicle_type": load.vehicle_type,
        "vehicle_identifier": load.vehicle_identifier,
        "cost_type": load.cost_type.value if load.cost_type else None,
        "dispatch_cost": float(load.dispatch_cost or 0),
        "cost_per_piece": float(load.cost_per_piece or 0),
        "shortfall_qty": load.shortfall_qty,
        "linked_repair_qty": load.linked_repair_qty,
        "linked_alteration_qty": load.linked_alteration_qty,
        "shortfall_reason": load.shortfall_reason,
        "shipped_at": str(load.shipped_at),
    }


async def update_dispatch_documents(
    db: AsyncSession,
    *,
    dispatch_load_id: UUID,
    document_status: str,
    invoice_uploaded: bool,
    packing_list_uploaded: bool,
    eway_bill_uploaded: bool,
    transporter_confirmation: bool,
    buyer_dispatch_approval: bool,
    updated_by: UUID | None,
    updated_role: str | None,
) -> DispatchLoad:
    load = await db.get(DispatchLoad, dispatch_load_id)
    if load is None:
        raise DomainError(status_code=404, detail="Dispatch load not found")
    old_values = {
        "document_status": load.document_status,
        "invoice_uploaded": load.invoice_uploaded,
        "packing_list_uploaded": load.packing_list_uploaded,
        "eway_bill_uploaded": load.eway_bill_uploaded,
        "transporter_confirmation": load.transporter_confirmation,
        "buyer_dispatch_approval": load.buyer_dispatch_approval,
    }
    load.document_status = document_status
    load.invoice_uploaded = invoice_uploaded
    load.packing_list_uploaded = packing_list_uploaded
    load.eway_bill_uploaded = eway_bill_uploaded
    load.transporter_confirmation = transporter_confirmation
    load.buyer_dispatch_approval = buyer_dispatch_approval
    await log_audit_event(
        db,
        action_type="dispatch_document_status_updated",
        entity_type="dispatch_load",
        entity_id=str(load.id),
        purchase_order_id=load.purchase_order_id,
        performed_by=updated_by,
        role=updated_role,
        old_value_json=old_values,
        new_value_json={
            "document_status": load.document_status,
            "invoice_uploaded": load.invoice_uploaded,
            "packing_list_uploaded": load.packing_list_uploaded,
            "eway_bill_uploaded": load.eway_bill_uploaded,
            "transporter_confirmation": load.transporter_confirmation,
            "buyer_dispatch_approval": load.buyer_dispatch_approval,
        },
    )
    await db.commit()
    await db.refresh(load)
    return load


async def get_shipped_quantity(db: AsyncSession, purchase_order_id: UUID, exclude_load_id: UUID | None = None) -> int:
    stmt = select(func.coalesce(func.sum(DispatchLoad.shipped_qty), 0)).where(
        DispatchLoad.purchase_order_id == purchase_order_id
    )
    if exclude_load_id is not None:
        stmt = stmt.where(DispatchLoad.id != exclude_load_id)
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def _get_stage(db: AsyncSession, purchase_order_id: UUID, stage: StageName) -> StageSummary:
    result = await db.execute(
        select(StageSummary).where(
            StageSummary.purchase_order_id == purchase_order_id,
            StageSummary.stage == stage,
        )
    )
    stage_summary = result.scalar_one_or_none()
    if stage_summary is None:
        raise DomainError(status_code=404, detail=f"{stage.value} stage not found")
    return stage_summary
    if payload.document_status == "blocked":
        raise DomainError(status_code=400, detail="Dispatch is blocked by missing documentation")
    if payload.document_status == "pending" and not (
        payload.invoice_uploaded
        and payload.packing_list_uploaded
        and payload.eway_bill_uploaded
        and payload.transporter_confirmation
    ):
        raise DomainError(status_code=400, detail="Required dispatch documents are incomplete")
