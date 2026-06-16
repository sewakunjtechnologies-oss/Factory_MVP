from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FabricPlanStatus, FabricVerificationStatus, POStatus, ReceiptStatus, StageName, StageStatus
from app.models.fabric import DebitNote, FabricInventory, FabricIssueToCutting, FabricPlan, FabricReceipt, SupplierReturn
from app.models.mill_requirement import MillOrderRequirement, MillOrderRequirementStatus
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import ReminderPriority, ReminderType
from app.models.stage import StageSummary
from app.services.exceptions import DomainError
from app.services.reminder_service import upsert_reminder


_TERMINAL_PO_STATUSES = {POStatus.completed, POStatus.cancelled}
_FABRIC_STATUS_FIXABLE = {POStatus.draft, POStatus.fabric_check_pending, POStatus.fabric_ready, POStatus.shortage}


def calculate_fabric_plan(
    order_qty_pcs: int,
    per_piece_fabric_usage_m: Decimal,
    wastage_percent: Decimal,
    roll_length_m: Optional[Decimal] = None,
) -> dict[str, Decimal | int | None]:
    if order_qty_pcs <= 0:
        raise DomainError(status_code=400, detail="order quantity must be greater than zero")
    if per_piece_fabric_usage_m <= 0:
        raise DomainError(status_code=400, detail="per-piece fabric usage must be greater than zero")
    if wastage_percent < 0:
        raise DomainError(status_code=400, detail="wastage percent cannot be negative")

    required_m = Decimal(order_qty_pcs) * per_piece_fabric_usage_m
    wastage_m = required_m * (wastage_percent / Decimal("100"))
    total_required_m = required_m + wastage_m
    rolls_required = None
    if roll_length_m is not None and roll_length_m > 0:
        rolls_required = int((total_required_m / roll_length_m).to_integral_value(rounding=ROUND_CEILING))
    return {
        "required_m": required_m.quantize(Decimal("0.001")),
        "wastage_m": wastage_m.quantize(Decimal("0.001")),
        "total_required_m": total_required_m.quantize(Decimal("0.001")),
        "rolls_required": rolls_required,
    }


async def get_matching_inventory(db: AsyncSession, product: Product) -> FabricInventory | None:
    result = await db.execute(
        select(FabricInventory).where(
            FabricInventory.fabric_type == product.fabric_type,
            FabricInventory.color == product.color,
            FabricInventory.gsm == product.gsm,
            FabricInventory.width == product.width,
        )
    )
    return result.scalar_one_or_none()


async def build_or_refresh_fabric_plan(db: AsyncSession, purchase_order: PurchaseOrder) -> FabricPlan:
    product = purchase_order.__dict__.get("product")
    if product is None:
        product = await db.get(Product, purchase_order.product_id)
    if product is None:
        raise DomainError(status_code=404, detail="Product not found")

    fabric_line = await get_product_fabric_line_for_po(db, purchase_order)
    pieces_in_stock = min(int(fabric_line.pieces_in_stock or 0), int(purchase_order.order_quantity_pcs)) if fabric_line else 0
    pieces_to_make = max(int(purchase_order.order_quantity_pcs) - pieces_in_stock, 0)
    per_piece_meters = (
        fabric_line.per_piece_meters
        if fabric_line is not None and fabric_line.per_piece_meters and fabric_line.per_piece_meters > 0
        else product.per_piece_fabric_usage_m
    )
    values = calculate_fabric_plan(
        pieces_to_make if pieces_to_make > 0 else 1,
        per_piece_meters,
        product.wastage_percent,
        product.roll_length_m,
    )
    if pieces_to_make == 0:
        values["required_m"] = Decimal("0.000")
        values["wastage_m"] = Decimal("0.000")
        values["total_required_m"] = Decimal("0.000")
        values["rolls_required"] = 0
    available_m = (
        Decimal(fabric_line.stock_meters or 0).quantize(Decimal("0.001"))
        if fabric_line is not None
        else await get_verified_available_meters(db, purchase_order.id, product)
    )
    if purchase_order.status in _TERMINAL_PO_STATUSES:
        available_m = values["total_required_m"]
    shortage_m = max(values["total_required_m"] - available_m, Decimal("0.000"))
    status = FabricPlanStatus.fabric_ready if shortage_m == 0 else FabricPlanStatus.shortage

    existing_plan = await db.execute(
        select(FabricPlan).where(FabricPlan.purchase_order_id == purchase_order.id)
    )
    plan = existing_plan.scalar_one_or_none()
    if plan is None:
        plan = FabricPlan(purchase_order_id=purchase_order.id)
        db.add(plan)

    plan.required_m = values["required_m"]
    plan.wastage_m = values["wastage_m"]
    plan.total_required_m = values["total_required_m"]
    plan.roll_length_m = product.roll_length_m if product.roll_length_m and product.roll_length_m > 0 else None
    plan.rolls_required = int(values["rolls_required"]) if values["rolls_required"] is not None else None
    plan.available_m = available_m
    plan.shortage_m = shortage_m.quantize(Decimal("0.001"))
    plan.status = status
    if purchase_order.status in _FABRIC_STATUS_FIXABLE:
        purchase_order.status = POStatus.fabric_ready if status == FabricPlanStatus.fabric_ready else POStatus.shortage
    if status == FabricPlanStatus.shortage and plan.shortage_m > 0 and purchase_order.status not in _TERMINAL_PO_STATUSES:
        await upsert_mill_order_requirement(db, purchase_order.id, plan, product)
    else:
        await close_mill_order_requirement_if_any(db, purchase_order.id)
    return plan


async def get_product_fabric_line_for_po(db: AsyncSession, purchase_order: PurchaseOrder) -> ProductFabricLine | None:
    code = (purchase_order.design_code_snapshot or "").strip()
    if not code:
        return None
    result = await db.execute(
        select(ProductFabricLine).where(
            ProductFabricLine.product_id == purchase_order.product_id,
            func.lower(ProductFabricLine.fabric_code) == code.lower(),
        )
    )
    return result.scalar_one_or_none()


async def get_verified_available_meters(db: AsyncSession, purchase_order_id: UUID, product: Product) -> Decimal:
    verified_result = await db.execute(
        select(func.coalesce(func.sum(func.coalesce(FabricReceipt.received_meters, FabricReceipt.received_length_m)), 0)).where(
            FabricReceipt.fabric_type == product.fabric_type,
            FabricReceipt.color == product.color,
            FabricReceipt.gsm == product.gsm,
            FabricReceipt.width == product.width,
            FabricReceipt.verification_status == FabricVerificationStatus.approved,
            FabricReceipt.status == ReceiptStatus.approved,
        )
    )
    verified_total = Decimal(verified_result.scalar_one() or 0)
    issued_result = await db.execute(
        select(func.coalesce(func.sum(FabricIssueToCutting.issued_meters), 0))
        .join(FabricReceipt, FabricReceipt.id == FabricIssueToCutting.fabric_receipt_id)
        .where(
            FabricReceipt.fabric_type == product.fabric_type,
            FabricReceipt.color == product.color,
            FabricReceipt.gsm == product.gsm,
            FabricReceipt.width == product.width,
        )
    )
    issued_total = Decimal(issued_result.scalar_one() or 0)
    verified_available = (verified_total - issued_total).quantize(Decimal("0.001"))
    if verified_available > 0:
        return verified_available
    inventory = await get_matching_inventory(db, product)
    return (inventory.available_length_m if inventory else Decimal("0.000")).quantize(Decimal("0.001"))


async def upsert_mill_order_requirement(db: AsyncSession, purchase_order_id: UUID, plan: FabricPlan, product: Product) -> MillOrderRequirement:
    result = await db.execute(
        select(MillOrderRequirement).where(MillOrderRequirement.purchase_order_id == purchase_order_id).order_by(MillOrderRequirement.created_at.desc())
    )
    requirement = result.scalars().first()
    if requirement is None:
        requirement = MillOrderRequirement(
            purchase_order_id=purchase_order_id,
            required_meters=float(plan.total_required_m),
            available_meters=float(plan.available_m),
            shortage_meters=float(plan.shortage_m),
            gsm=float(product.gsm),
            fabric_type=product.fabric_type,
            design=product.design,
            color=product.color,
            suggested_order_meters=float(plan.shortage_m),
            status=MillOrderRequirementStatus.pending_mill_selection,
        )
        db.add(requirement)
    else:
        requirement.required_meters = float(plan.total_required_m)
        requirement.available_meters = float(plan.available_m)
        requirement.shortage_meters = float(plan.shortage_m)
        requirement.suggested_order_meters = float(plan.shortage_m)
        requirement.status = MillOrderRequirementStatus.pending_mill_selection
    await upsert_reminder(
        db,
        purchase_order_id=purchase_order_id,
        reminder_type=ReminderType.fabric_order_pending,
        title="Fabric order pending",
        message="Fabric shortage exists for PO. Mill order needs to be created.",
        due_date=date.today(),
        priority=ReminderPriority.high,
    )
    return requirement


async def close_mill_order_requirement_if_any(db: AsyncSession, purchase_order_id: UUID) -> None:
    result = await db.execute(
        select(MillOrderRequirement).where(MillOrderRequirement.purchase_order_id == purchase_order_id).order_by(MillOrderRequirement.created_at.desc())
    )
    requirement = result.scalars().first()
    if requirement is not None and requirement.status != MillOrderRequirementStatus.closed:
        requirement.status = MillOrderRequirementStatus.closed


async def list_fabric_inventory(db: AsyncSession) -> list[FabricInventory]:
    result = await db.execute(select(FabricInventory).order_by(FabricInventory.fabric_type, FabricInventory.color))
    return list(result.scalars().all())


async def get_fabric_inventory(db: AsyncSession, inventory_id: UUID) -> FabricInventory:
    inventory = await db.get(FabricInventory, inventory_id)
    if inventory is None:
        raise DomainError(status_code=404, detail="Fabric inventory row not found")
    return inventory


async def upsert_fabric_inventory(db: AsyncSession, payload: object) -> FabricInventory:
    result = await db.execute(
        select(FabricInventory).where(
            FabricInventory.fabric_type == payload.fabric_type,
            FabricInventory.color == payload.color,
            FabricInventory.gsm == payload.gsm,
            FabricInventory.width == payload.width,
        )
    )
    inventory = result.scalar_one_or_none()
    if inventory is None:
        inventory = FabricInventory(
            fabric_type=payload.fabric_type,
            color=payload.color,
            gsm=payload.gsm,
            width=payload.width,
            available_length_m=payload.available_length_m,
            approximate_rolls=payload.approximate_rolls,
        )
        db.add(inventory)
    else:
        inventory.available_length_m = payload.available_length_m
        inventory.approximate_rolls = payload.approximate_rolls
    await db.commit()
    await db.refresh(inventory)
    return inventory


async def update_fabric_inventory(db: AsyncSession, inventory_id: UUID, payload: object) -> FabricInventory:
    inventory = await get_fabric_inventory(db, inventory_id)
    old_spec = _inventory_spec(inventory)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return inventory

    for field, value in updates.items():
        setattr(inventory, field, value)
    await db.flush()
    await _refresh_pos_for_inventory_specs(db, [old_spec, _inventory_spec(inventory)])
    await db.commit()
    await db.refresh(inventory)
    return inventory


async def delete_fabric_inventory(db: AsyncSession, inventory_id: UUID) -> None:
    inventory = await get_fabric_inventory(db, inventory_id)
    old_spec = _inventory_spec(inventory)
    await db.delete(inventory)
    await db.flush()
    await _refresh_pos_for_inventory_specs(db, [old_spec])
    await db.commit()


async def receive_fabric(db: AsyncSession, payload: object) -> dict[str, object]:
    if payload.status not in (ReceiptStatus.approved, ReceiptStatus.failed):
        raise DomainError(status_code=400, detail="fabric receipt must be approved or failed")

    receipt = FabricReceipt(
        purchase_order_id=payload.purchase_order_id,
        supplier_name=payload.supplier_name,
        fabric_type=payload.fabric_type,
        color=payload.color,
        gsm=payload.gsm,
        width=payload.width,
        received_length_m=payload.available_length_m,
        approximate_rolls=payload.approximate_rolls,
        status=payload.status,
        quality_notes=payload.quality_notes,
        received_width=payload.received_width,
        received_gsm=payload.received_gsm,
        received_rate_per_meter=payload.received_rate_per_meter,
        received_meters=payload.received_meters,
        verified_by=payload.verified_by,
        verification_date=payload.verification_date,
        verification_status=payload.verification_status,
        mismatch_reason=payload.mismatch_reason,
        action_taken=payload.action_taken,
        assigned_to=payload.assigned_to,
        responsible_role=payload.responsible_role,
        completed_by=payload.completed_by,
        completed_at=payload.completed_at,
        remarks=payload.remarks,
        received_at=payload.received_at,
    )
    db.add(receipt)
    await db.flush()

    supplier_return: SupplierReturn | None = None
    debit_note: DebitNote | None = None
    refreshed_plan: FabricPlan | None = None
    if payload.status == ReceiptStatus.approved and payload.verification_status.value == "approved":
        inventory = await get_inventory_by_spec(db, payload.fabric_type, payload.color, payload.gsm, payload.width)
        if inventory is None:
            inventory = FabricInventory(
                fabric_type=payload.fabric_type,
                color=payload.color,
                gsm=payload.gsm,
                width=payload.width,
                available_length_m=payload.available_length_m,
                approximate_rolls=payload.approximate_rolls,
            )
            db.add(inventory)
        else:
            inventory.available_length_m += payload.available_length_m
            if payload.approximate_rolls is not None:
                inventory.approximate_rolls = (inventory.approximate_rolls or 0) + payload.approximate_rolls
    else:
        reason = payload.quality_notes or "Fabric quality failed"
        supplier_return = SupplierReturn(
            fabric_receipt_id=receipt.id,
            supplier_name=payload.supplier_name,
            returned_length_m=payload.available_length_m,
            reason=reason,
            returned_at=payload.received_at,
        )
        debit_note = DebitNote(
            fabric_receipt_id=receipt.id,
            supplier_name=payload.supplier_name,
            amount=payload.debit_amount,
            reason=reason,
            note_date=payload.received_at,
        )
        db.add_all([supplier_return, debit_note])

    if payload.purchase_order_id is not None:
        po = await db.get(PurchaseOrder, payload.purchase_order_id)
        if po is not None:
            await db.refresh(po, attribute_names=["product", "fabric_plan"])
            refreshed_plan = await build_or_refresh_fabric_plan(db, po)
            if payload.status == ReceiptStatus.approved and refreshed_plan.status == FabricPlanStatus.fabric_ready:
                await _release_fabric_to_cutting(db, po)

    await db.commit()
    await db.refresh(receipt)
    if supplier_return is not None:
        await db.refresh(supplier_return)
    if debit_note is not None:
        await db.refresh(debit_note)
    if refreshed_plan is not None:
        await db.refresh(refreshed_plan)
    return {
        "receipt": receipt,
        "supplier_return": supplier_return,
        "debit_note": debit_note,
        "refreshed_plan": refreshed_plan,
    }


async def get_inventory_by_spec(
    db: AsyncSession,
    fabric_type: str,
    color: str,
    gsm: Decimal,
    width: Decimal,
) -> FabricInventory | None:
    result = await db.execute(
        select(FabricInventory).where(
            FabricInventory.fabric_type == fabric_type,
            FabricInventory.color == color,
            FabricInventory.gsm == gsm,
            FabricInventory.width == width,
        )
    )
    return result.scalar_one_or_none()


def _inventory_spec(inventory: FabricInventory) -> tuple[str, str, Decimal, Decimal]:
    return (
        inventory.fabric_type,
        inventory.color,
        Decimal(str(inventory.gsm)),
        Decimal(str(inventory.width)),
    )


async def _refresh_pos_for_inventory_specs(
    db: AsyncSession,
    specs: list[tuple[str, str, Decimal, Decimal]],
) -> None:
    unique_specs = list(dict.fromkeys(specs))
    if not unique_specs:
        return
    conditions = [
        and_(
            Product.fabric_type == fabric_type,
            Product.color == color,
            Product.gsm == gsm,
            Product.width == width,
        )
        for fabric_type, color, gsm, width in unique_specs
    ]
    products = (await db.execute(select(Product).where(or_(*conditions)))).scalars().all()
    if not products:
        return
    pos = (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.product_id.in_([product.id for product in products]))
    )).scalars().all()
    for po in pos:
        await build_or_refresh_fabric_plan(db, po)


async def list_shortage_plans(db: AsyncSession) -> list[FabricPlan]:
    result = await db.execute(select(FabricPlan).where(FabricPlan.status == FabricPlanStatus.shortage))
    return list(result.scalars().all())


async def list_fabric_receipts(db: AsyncSession) -> list[FabricReceipt]:
    result = await db.execute(select(FabricReceipt).order_by(FabricReceipt.received_at.desc(), FabricReceipt.created_at.desc()))
    return list(result.scalars().all())


async def list_supplier_returns(db: AsyncSession) -> list[SupplierReturn]:
    result = await db.execute(select(SupplierReturn).order_by(SupplierReturn.returned_at.desc(), SupplierReturn.created_at.desc()))
    return list(result.scalars().all())


async def list_debit_notes(db: AsyncSession) -> list[DebitNote]:
    result = await db.execute(select(DebitNote).order_by(DebitNote.note_date.desc(), DebitNote.created_at.desc()))
    return list(result.scalars().all())


async def mark_fabric_receipt_failed(
    db: AsyncSession,
    receipt_id: UUID | None = None,
    purchase_order_id: UUID | None = None,
    reason: str = "Fabric quality failed",
    debit_amount: Decimal | None = None,
) -> dict[str, object]:
    statement = select(FabricReceipt)
    if receipt_id is not None:
        statement = statement.where(FabricReceipt.id == receipt_id)
    elif purchase_order_id is not None:
        statement = statement.where(FabricReceipt.purchase_order_id == purchase_order_id).order_by(FabricReceipt.created_at.desc())
    else:
        raise DomainError(status_code=400, detail="receipt_id or purchase_order_id is required")

    result = await db.execute(statement)
    receipt = result.scalars().first()
    if receipt is None:
        raise DomainError(status_code=404, detail="Fabric receipt not found")

    receipt.status = ReceiptStatus.failed
    receipt.quality_notes = reason
    receipt.verification_status = FabricVerificationStatus.rejected
    supplier_return = SupplierReturn(
        fabric_receipt_id=receipt.id,
        supplier_name=receipt.supplier_name,
        returned_length_m=receipt.received_length_m,
        reason=reason,
        returned_at=receipt.received_at,
    )
    debit_note = DebitNote(
        fabric_receipt_id=receipt.id,
        supplier_name=receipt.supplier_name,
        amount=debit_amount,
        reason=reason,
        note_date=receipt.received_at,
    )
    db.add_all([supplier_return, debit_note])
    if receipt.purchase_order_id is not None:
        po = await db.get(PurchaseOrder, receipt.purchase_order_id)
        if po is not None:
            await db.refresh(po, attribute_names=["product", "fabric_plan"])
            await build_or_refresh_fabric_plan(db, po)
    await db.commit()
    await db.refresh(receipt)
    await db.refresh(supplier_return)
    await db.refresh(debit_note)
    return {"receipt": receipt, "supplier_return": supplier_return, "debit_note": debit_note}


async def create_debit_note(
    db: AsyncSession,
    supplier_return_id: UUID | None,
    amount: Decimal,
    issue_date: date,
    reason: str,
) -> DebitNote:
    supplier_return = await db.get(SupplierReturn, supplier_return_id) if supplier_return_id is not None else None
    if supplier_return is None:
        raise DomainError(status_code=404, detail="Supplier return not found")
    debit_note = DebitNote(
        fabric_receipt_id=supplier_return.fabric_receipt_id,
        supplier_name=supplier_return.supplier_name,
        amount=amount,
        reason=reason,
        note_date=issue_date,
    )
    db.add(debit_note)
    await db.commit()
    await db.refresh(debit_note)
    return debit_note


async def refresh_po_fabric_plan(db: AsyncSession, purchase_order_id: UUID) -> FabricPlan:
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == purchase_order_id))
    purchase_order = result.scalar_one_or_none()
    if purchase_order is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    await db.refresh(purchase_order, attribute_names=["product", "fabric_plan"])
    plan = await build_or_refresh_fabric_plan(db, purchase_order)
    if plan.status == FabricPlanStatus.fabric_ready:
        await _release_fabric_to_cutting(db, purchase_order)
    await db.commit()
    await db.refresh(plan)
    return plan


async def _release_fabric_to_cutting(db: AsyncSession, purchase_order: PurchaseOrder) -> None:
    result = await db.execute(
        select(StageSummary).where(StageSummary.purchase_order_id == purchase_order.id)
    )
    stages = {stage.stage: stage for stage in result.scalars().all()}
    fabric_stage = stages.get(StageName.fabric_ready)
    cutting_stage = stages.get(StageName.cutting)
    if fabric_stage is None or cutting_stage is None:
        return

    order_qty = purchase_order.order_quantity_pcs
    fabric_stage.completed_qty = max(fabric_stage.completed_qty, order_qty)
    fabric_stage.approved_qty = max(fabric_stage.approved_qty, order_qty)
    fabric_stage.pending_qty = max(fabric_stage.input_qty - fabric_stage.completed_qty, 0)
    fabric_stage.status = StageStatus.completed

    remaining_release = max(fabric_stage.approved_qty - fabric_stage.moved_to_next_qty, 0)
    if remaining_release == 0:
        return
    cutting_stage.input_qty += remaining_release
    cutting_stage.pending_qty += remaining_release
    cutting_stage.status = StageStatus.in_progress
    fabric_stage.moved_to_next_qty += remaining_release
