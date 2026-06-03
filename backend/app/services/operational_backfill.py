from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import FabricPlanStatus, POStatus, StageName, StageStatus
from app.models.fabric import FabricInventory, FabricPlan
from app.models.mill_requirement import MillOrderRequirement, MillOrderRequirementStatus
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageSummary


TERMINAL_PO_STATUSES = {POStatus.completed, POStatus.cancelled}
STAGE_SEQUENCE: tuple[StageName, ...] = (
    StageName.fabric_ready,
    StageName.cutting,
    StageName.stitching,
    StageName.size_inspection,
    StageName.quality_check,
    StageName.packing,
    StageName.dispatch,
)
_FABRIC_STATUS_FIXABLE = {POStatus.draft, POStatus.fabric_check_pending, POStatus.fabric_ready, POStatus.shortage}
_WORKFLOW_STATUS_TO_STAGE = {
    POStatus.fabric_ready: StageName.cutting,
    POStatus.cutting: StageName.cutting,
    POStatus.stitching: StageName.stitching,
    POStatus.size_inspection: StageName.size_inspection,
    POStatus.quality_check: StageName.quality_check,
    POStatus.packing: StageName.packing,
    POStatus.dispatch: StageName.dispatch,
    POStatus.partially_dispatched: StageName.dispatch,
    POStatus.dispatched_with_exception: StageName.dispatch,
}


async def ensure_all_operational_data(db: AsyncSession) -> None:
    """Backfill derived rows for imported POs.

    The June sheet import inserted POs directly, bypassing normal create hooks
    that make fabric plans and stage summaries. Owner-facing reads depend on
    those rows, so this idempotent backfill keeps imported data queryable
    without hardcoding answers in the assistant or dashboard.
    """
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.product))
        .order_by(PurchaseOrder.created_at.asc())
    )
    changed = False
    for po in result.scalars().all():
        changed = await ensure_po_operational_data(db, po, commit=False) or changed
    if changed:
        await db.commit()


async def ensure_po_operational_data(db: AsyncSession, po: PurchaseOrder, *, commit: bool = True) -> bool:
    changed = False
    product = await _load_product(db, po)
    if product is None:
        return False

    plan, plan_changed = await _ensure_fabric_plan(db, po, product)
    changed = plan_changed or changed
    stage_changed = await _ensure_stage_summaries(db, po)
    changed = stage_changed or changed
    requirement_changed = await _sync_mill_requirement(db, po, product, plan)
    changed = requirement_changed or changed

    if commit and changed:
        await db.commit()
    return changed


async def repair_future_actual_delivery_dates(db: AsyncSession, *, today: date | None = None) -> int:
    """Clear impossible future actual-delivery dates.

    This is intentionally separate from read backfill so production reads don't
    silently rewrite historical business facts. The repair script calls it for
    the local demo database after audit approval.
    """
    today = today or date.today()
    result = await db.execute(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.actual_delivery_date.is_not(None),
            PurchaseOrder.actual_delivery_date > today,
            PurchaseOrder.status == POStatus.completed,
        )
        .options(selectinload(PurchaseOrder.product))
    )
    repaired = 0
    for po in result.scalars().all():
        product = await _load_product(db, po)
        if product is None:
            continue
        po.actual_delivery_date = None
        line = await _find_fabric_line(db, po)
        values = await _plan_values(db, po, product, line, force_no_shortage=False)
        po.status = POStatus.fabric_ready if values["shortage_m"] <= 0 else POStatus.shortage
        await _delete_stage_summaries(db, po.id)
        repaired += 1
    if repaired:
        await db.commit()
    return repaired


async def _load_product(db: AsyncSession, po: PurchaseOrder) -> Product | None:
    product = po.__dict__.get("product")
    if product is not None:
        return product
    return await db.get(Product, po.product_id)


async def _find_fabric_line(db: AsyncSession, po: PurchaseOrder) -> ProductFabricLine | None:
    code = (po.design_code_snapshot or "").strip()
    if not code:
        result = await db.execute(select(ProductFabricLine).where(ProductFabricLine.product_id == po.product_id))
        return result.scalars().first()
    result = await db.execute(
        select(ProductFabricLine).where(
            ProductFabricLine.product_id == po.product_id,
            func.lower(ProductFabricLine.fabric_code) == code.lower(),
        )
    )
    line = result.scalar_one_or_none()
    if line is not None:
        return line
    # June PDF rows keep a short internal PO code (JUNE-001) but the fabric
    # line stores the full owner-facing PO category. Imported products are
    # one-product/one-line, so this fallback keeps backfill from inventing a
    # shortage when the exact snapshot code is intentionally different.
    result = await db.execute(select(ProductFabricLine).where(ProductFabricLine.product_id == po.product_id))
    return result.scalars().first()


async def _plan_values(
    db: AsyncSession,
    po: PurchaseOrder,
    product: Product,
    line: ProductFabricLine | None,
    *,
    force_no_shortage: bool,
) -> dict[str, Decimal | int | None]:
    per_piece = Decimal(line.per_piece_meters) if line and line.per_piece_meters and line.per_piece_meters > 0 else Decimal(product.per_piece_fabric_usage_m)
    wastage_percent = Decimal(product.wastage_percent or 0)
    pieces_in_stock = min(int(line.pieces_in_stock or 0), int(po.order_quantity_pcs)) if line else 0
    pieces_to_make = max(int(po.order_quantity_pcs) - pieces_in_stock, 0)
    required_m = (Decimal(pieces_to_make) * per_piece).quantize(Decimal("0.001"))
    wastage_m = (required_m * (wastage_percent / Decimal("100"))).quantize(Decimal("0.001"))
    total_required_m = (required_m + wastage_m).quantize(Decimal("0.001"))
    roll_length = Decimal(product.roll_length_m) if product.roll_length_m and product.roll_length_m > 0 else None
    rolls_required = None
    if roll_length:
        rolls_required = int((total_required_m / roll_length).to_integral_value(rounding=ROUND_CEILING))

    if force_no_shortage:
        available_m = total_required_m
    elif line is not None:
        available_m = Decimal(line.stock_meters or 0).quantize(Decimal("0.001"))
    else:
        available_m = await _matching_inventory_meters(db, product)
    shortage_m = max(total_required_m - available_m, Decimal("0.000")).quantize(Decimal("0.001"))
    return {
        "required_m": required_m,
        "wastage_m": wastage_m,
        "total_required_m": total_required_m,
        "roll_length_m": roll_length,
        "rolls_required": rolls_required,
        "available_m": available_m,
        "shortage_m": shortage_m,
    }


async def _matching_inventory_meters(db: AsyncSession, product: Product) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(FabricInventory.available_length_m), 0)).where(
            FabricInventory.fabric_type == product.fabric_type,
            FabricInventory.color == product.color,
            FabricInventory.gsm == product.gsm,
            FabricInventory.width == product.width,
        )
    )
    return Decimal(result.scalar_one() or 0).quantize(Decimal("0.001"))


async def _ensure_fabric_plan(db: AsyncSession, po: PurchaseOrder, product: Product) -> tuple[FabricPlan, bool]:
    result = await db.execute(select(FabricPlan).where(FabricPlan.purchase_order_id == po.id))
    plan = result.scalar_one_or_none()
    line = await _find_fabric_line(db, po)
    values = await _plan_values(db, po, product, line, force_no_shortage=po.status in TERMINAL_PO_STATUSES)
    status = FabricPlanStatus.fabric_ready if values["shortage_m"] <= 0 else FabricPlanStatus.shortage
    if plan is None:
        plan = FabricPlan(
            purchase_order_id=po.id,
            required_m=values["required_m"],
            wastage_m=values["wastage_m"],
            total_required_m=values["total_required_m"],
            roll_length_m=values["roll_length_m"],
            rolls_required=values["rolls_required"],
            available_m=values["available_m"],
            shortage_m=values["shortage_m"],
            status=status,
        )
        db.add(plan)
        changed = True
    else:
        changed = False
    updates = {
        "required_m": values["required_m"],
        "wastage_m": values["wastage_m"],
        "total_required_m": values["total_required_m"],
        "roll_length_m": values["roll_length_m"],
        "rolls_required": values["rolls_required"],
        "available_m": values["available_m"],
        "shortage_m": values["shortage_m"],
        "status": status,
    }
    for key, value in updates.items():
        if getattr(plan, key, None) != value:
            setattr(plan, key, value)
            changed = True

    if po.status in _FABRIC_STATUS_FIXABLE:
        next_status = POStatus.fabric_ready if status == FabricPlanStatus.fabric_ready else POStatus.shortage
        if po.status != next_status:
            po.status = next_status
            changed = True
    return plan, changed


async def _sync_mill_requirement(db: AsyncSession, po: PurchaseOrder, product: Product, plan: FabricPlan) -> bool:
    result = await db.execute(
        select(MillOrderRequirement)
        .where(MillOrderRequirement.purchase_order_id == po.id)
        .order_by(MillOrderRequirement.created_at.desc())
    )
    requirement = result.scalars().first()
    shortage = Decimal(plan.shortage_m or 0)
    should_be_open = shortage > 0 and po.status not in TERMINAL_PO_STATUSES
    if not should_be_open:
        if requirement and requirement.status != MillOrderRequirementStatus.closed:
            requirement.status = MillOrderRequirementStatus.closed
            return True
        return False

    values = {
        "required_meters": float(plan.total_required_m),
        "available_meters": float(plan.available_m),
        "shortage_meters": float(plan.shortage_m),
        "gsm": float(product.gsm) if product.gsm is not None else None,
        "fabric_type": product.fabric_type,
        "design": po.design_code_snapshot or product.design,
        "color": product.color,
        "suggested_order_meters": float(plan.shortage_m),
        "status": MillOrderRequirementStatus.pending_mill_selection,
    }
    if requirement is None:
        db.add(MillOrderRequirement(purchase_order_id=po.id, **values))
        return True
    changed = False
    for key, value in values.items():
        if getattr(requirement, key) != value:
            setattr(requirement, key, value)
            changed = True
    return changed


async def _delete_stage_summaries(db: AsyncSession, purchase_order_id: UUID) -> None:
    result = await db.execute(select(StageSummary).where(StageSummary.purchase_order_id == purchase_order_id))
    for row in result.scalars().all():
        await db.delete(row)


async def _ensure_stage_summaries(db: AsyncSession, po: PurchaseOrder) -> bool:
    result = await db.execute(select(StageSummary).where(StageSummary.purchase_order_id == po.id))
    existing = {row.stage: row for row in result.scalars().all()}
    changed = False
    for index, stage in enumerate(STAGE_SEQUENCE):
        if stage in existing:
            continue
        attrs = _stage_defaults(po, stage, index)
        db.add(StageSummary(purchase_order_id=po.id, **attrs))
        changed = True
    return changed


def _stage_defaults(po: PurchaseOrder, stage: StageName, sequence: int) -> dict:
    qty = int(po.order_quantity_pcs)
    if po.status == POStatus.completed:
        return {
            "stage": stage,
            "sequence": sequence,
            "input_qty": qty,
            "completed_qty": qty,
            "approved_qty": qty,
            "moved_to_next_qty": 0 if stage == StageName.dispatch else qty,
            "pending_qty": 0,
            "status": StageStatus.completed,
        }

    active_stage = _WORKFLOW_STATUS_TO_STAGE.get(po.status)
    if po.status == POStatus.shortage or active_stage is None:
        if stage == StageName.fabric_ready:
            return _stage_row(stage, sequence, qty, 0, StageStatus.blocked)
        return _stage_row(stage, sequence, 0, 0, StageStatus.not_started)

    active_index = STAGE_SEQUENCE.index(active_stage)
    stage_index = STAGE_SEQUENCE.index(stage)
    if stage_index < active_index:
        return {
            "stage": stage,
            "sequence": sequence,
            "input_qty": qty,
            "completed_qty": qty,
            "approved_qty": qty,
            "moved_to_next_qty": qty,
            "pending_qty": 0,
            "status": StageStatus.completed,
        }
    if stage_index == active_index:
        return _stage_row(stage, sequence, qty, 0, StageStatus.in_progress)
    return _stage_row(stage, sequence, 0, 0, StageStatus.not_started)


def _stage_row(stage: StageName, sequence: int, input_qty: int, completed_qty: int, status: StageStatus) -> dict:
    return {
        "stage": stage,
        "sequence": sequence,
        "input_qty": input_qty,
        "completed_qty": completed_qty,
        "approved_qty": completed_qty,
        "moved_to_next_qty": completed_qty,
        "pending_qty": max(input_qty - completed_qty, 0),
        "status": status,
    }
