from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.enums import FabricDesignCategory, PODesignStatus, POStatus, StageName, StageStatus
from app.models.fabric_design import FabricDesign
from app.schemas.fabric_design import FabricDesignCreate
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageSummary
from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.audit_service import log_audit_event
from app.services.exceptions import DomainError
from app.services.fabric_planning import build_or_refresh_fabric_plan
from app.services.fabric_design_service import create_fabric_design, normalize_category
from app.services.operational_backfill import ensure_all_operational_data, ensure_po_operational_data


STAGE_SEQUENCE: tuple[StageName, ...] = (
    StageName.fabric_ready,
    StageName.cutting,
    StageName.stitching,
    StageName.size_inspection,
    StageName.quality_check,
    StageName.packing,
    StageName.dispatch,
)


async def create_purchase_order(
    db: AsyncSession,
    payload: PurchaseOrderCreate,
    created_by: UUID | None,
) -> PurchaseOrder:
    existing = await db.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == payload.po_number))
    if existing.scalar_one_or_none() is not None:
        raise DomainError(status_code=409, detail="PO number already exists")

    product_result = await db.execute(select(Product).where(Product.id == payload.product_id))
    product = product_result.scalar_one_or_none()
    if product is None:
        raise DomainError(status_code=404, detail="Product not found")

    design_payload = payload.model_dump(
        exclude={
            "fabric_design_id",
            "custom_design_name",
            "custom_design_photo_url",
            "save_custom_design_to_library",
        }
    )
    design_payload.update(
        {
            "fabric_design_id": None,
            "design_name_snapshot": None,
            "design_code_snapshot": None,
            "design_image_url_snapshot": None,
            "design_status": PODesignStatus.not_provided,
        }
    )

    selected_design: FabricDesign | None = None
    if payload.fabric_design_id is not None:
        selected_design = await db.get(FabricDesign, payload.fabric_design_id)
        if selected_design is None:
            raise DomainError(status_code=404, detail="Fabric design not found")
        if not selected_design.is_active:
            raise DomainError(status_code=400, detail="Selected fabric design is inactive")
        product_category = normalize_category(product.product_category)
        if selected_design.category != product_category:
            raise DomainError(status_code=400, detail="Selected design category does not match product category")
        design_payload["fabric_design_id"] = selected_design.id
        design_payload["design_name_snapshot"] = selected_design.design_name
        design_payload["design_code_snapshot"] = selected_design.design_code
        design_payload["design_image_url_snapshot"] = selected_design.image_url
        design_payload["design_status"] = PODesignStatus.selected_from_library
    elif payload.custom_design_name or payload.custom_design_photo_url:
        custom_name = (payload.custom_design_name or "").strip()
        custom_photo = (payload.custom_design_photo_url or "").strip() or None
        design_payload["design_name_snapshot"] = custom_name or "Custom Design"
        design_payload["design_code_snapshot"] = None
        design_payload["design_image_url_snapshot"] = custom_photo
        design_payload["design_status"] = PODesignStatus.custom_design
        if payload.save_custom_design_to_library:
            created_design = await create_fabric_design(
                db,
                payload=_build_design_payload_for_po(product.product_category, custom_name, custom_photo),
                created_by=created_by,
                commit=False,
            )
            design_payload["fabric_design_id"] = created_design.id
            design_payload["design_code_snapshot"] = created_design.design_code
            design_payload["design_name_snapshot"] = created_design.design_name
            design_payload["design_image_url_snapshot"] = created_design.image_url
            design_payload["design_status"] = PODesignStatus.selected_from_library

    po = PurchaseOrder(**design_payload, created_by=created_by)
    po.product = product
    db.add(po)
    await db.flush()

    await build_or_refresh_fabric_plan(db, po)
    _create_stage_summaries(db, po)
    await log_audit_event(
        db,
        action_type="po_created",
        entity_type="purchase_order",
        entity_id=str(po.id),
        purchase_order_id=po.id,
        performed_by=created_by,
        role="owner_or_manager",
        new_value_json={"po_number": po.po_number, "order_quantity_pcs": po.order_quantity_pcs, "status": po.status.value},
    )
    await db.commit()
    return await get_purchase_order(db, po.id)


async def list_purchase_orders(db: AsyncSession) -> list[PurchaseOrder]:
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
    pos = list(result.scalars().all())
    await _attach_stock_for_fabric(db, pos)
    return pos


async def update_purchase_order_priority(
    db: AsyncSession,
    *,
    purchase_order_id: UUID,
    priority_level: str,
    priority_reason: str | None,
    updated_by: UUID | None,
    updated_role: str | None,
) -> PurchaseOrder:
    po = await db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    old_level = po.priority_level
    old_reason = po.priority_reason
    po.priority_level = priority_level
    po.priority_reason = priority_reason
    po.priority_updated_by = updated_by
    po.priority_updated_at = datetime.now(timezone.utc)
    await log_audit_event(
        db,
        action_type="po_priority_changed",
        entity_type="purchase_order",
        entity_id=str(po.id),
        purchase_order_id=po.id,
        performed_by=updated_by,
        role=updated_role,
        old_value_json={"priority_level": old_level, "priority_reason": old_reason},
        new_value_json={"priority_level": priority_level, "priority_reason": priority_reason},
    )
    await db.commit()
    return await get_purchase_order(db, purchase_order_id)


async def get_purchase_order(db: AsyncSession, purchase_order_id: UUID) -> PurchaseOrder:
    po = await db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    await ensure_po_operational_data(db, po)
    result = await db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == purchase_order_id)
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
        )
    )
    purchase_order = result.scalar_one_or_none()
    if purchase_order is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    await _attach_stock_for_fabric(db, [purchase_order])
    return purchase_order


async def _attach_stock_for_fabric(db: AsyncSession, pos: list[PurchaseOrder]) -> None:
    """For each PO, look up how many pieces of its fabric we have in stock and
    attach `pieces_in_stock_for_fabric` + `pieces_to_make` as in-memory attrs
    that the Pydantic read schema picks up via `from_attributes=True`.

    Join key is (product_id, design_code_snapshot) → product_fabric_lines row.
    Empty / missing fabric_code → 0 in stock (no link possible).
    """
    from app.models.product_fabric_line import ProductFabricLine

    if not pos:
        return

    # Build a unique set of (product_id, fabric_code) pairs we care about, then
    # one query instead of N. SQLite handles ~50 POs in a single round-trip.
    keys = {
        (po.product_id, (po.design_code_snapshot or "").strip())
        for po in pos
        if po.design_code_snapshot
    }
    stock: dict[tuple, int] = {}
    if keys:
        # SQLAlchemy doesn't have a clean way to do composite IN for two cols, so
        # we fetch all lines for the involved product_ids and filter in Python.
        product_ids = {pid for pid, _ in keys}
        rows = (await db.execute(
            select(ProductFabricLine).where(ProductFabricLine.product_id.in_(product_ids))
        )).scalars().all()
        for row in rows:
            stock[(row.product_id, row.fabric_code.strip())] = int(row.pieces_in_stock or 0)

    for po in pos:
        in_stock = stock.get((po.product_id, (po.design_code_snapshot or "").strip()), 0)
        # Cap at the ordered qty — a fabric_line stock of 9999 doesn't mean
        # the PO needs 9999 less; only as many as it actually ordered.
        in_stock = min(in_stock, po.order_quantity_pcs)
        # Set as plain attrs — Pydantic's from_attributes reads via getattr.
        po.pieces_in_stock_for_fabric = in_stock  # type: ignore[attr-defined]
        po.pieces_to_make = max(0, po.order_quantity_pcs - in_stock)  # type: ignore[attr-defined]


async def update_purchase_order(
    db: AsyncSession,
    *,
    purchase_order_id: UUID,
    fields: dict,
    updated_by: UUID | None,
) -> PurchaseOrder:
    """Patch any subset of PO fields. Reuses the priority audit shape so the
    edit history is consistent across all edits."""
    po = await db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")

    # If po_number is changed, make sure the new one isn't taken.
    new_po_number = fields.get("po_number")
    if new_po_number and new_po_number != po.po_number:
        clash = await db.execute(
            select(PurchaseOrder).where(PurchaseOrder.po_number == new_po_number)
        )
        if clash.scalar_one_or_none() is not None:
            raise DomainError(status_code=409, detail=f"PO number {new_po_number!r} already exists")

    # If product_id is changed, validate it exists.
    new_product_id = fields.get("product_id")
    if new_product_id is not None and new_product_id != po.product_id:
        product = await db.get(Product, new_product_id)
        if product is None:
            raise DomainError(status_code=404, detail="Product not found")

    # Date sanity: promise_delivery_date must be >= order_date.
    new_order_date = fields.get("order_date", po.order_date)
    new_promise_date = fields.get("promise_delivery_date", po.promise_delivery_date)
    if new_promise_date < new_order_date:
        raise DomainError(status_code=400, detail="promise_delivery_date cannot be before order_date")

    old_snapshot = {
        "po_number": po.po_number,
        "order_quantity_pcs": po.order_quantity_pcs,
        "status": po.status.value if po.status else None,
        "promise_delivery_date": str(po.promise_delivery_date),
    }
    for key, value in fields.items():
        if hasattr(po, key):
            setattr(po, key, value)

    await log_audit_event(
        db,
        action_type="po_updated",
        entity_type="purchase_order",
        entity_id=str(po.id),
        purchase_order_id=po.id,
        performed_by=updated_by,
        role="owner_or_manager",
        old_value_json=old_snapshot,
        new_value_json=fields,
    )
    await db.commit()
    return await get_purchase_order(db, purchase_order_id)


async def delete_purchase_order(
    db: AsyncSession,
    *,
    purchase_order_id: UUID,
    deleted_by: UUID | None,
) -> None:
    """Hard delete + audit row. SQLAlchemy cascade handles fabric_plan,
    stage_summaries, alerts, reminders, dispatch_loads (all set
    cascade="all, delete-orphan" on the PurchaseOrder relationships)."""
    po = await db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")
    snapshot = {"po_number": po.po_number, "order_quantity_pcs": po.order_quantity_pcs}
    await log_audit_event(
        db,
        action_type="po_deleted",
        entity_type="purchase_order",
        entity_id=str(po.id),
        purchase_order_id=po.id,
        performed_by=deleted_by,
        role="owner_or_manager",
        old_value_json=snapshot,
        new_value_json=None,
    )
    await db.flush()
    # Detach audit history so the FK doesn't block the delete; keep the rows
    # for posterity (purchase_order_id is nullable).
    await db.execute(
        update(AuditLog)
        .where(AuditLog.purchase_order_id == purchase_order_id)
        .values(purchase_order_id=None)
    )
    await db.delete(po)
    await db.commit()


def _create_stage_summaries(db: AsyncSession, purchase_order: PurchaseOrder) -> None:
    fabric_ready = purchase_order.status == POStatus.fabric_ready
    for index, stage in enumerate(STAGE_SEQUENCE):
        input_qty = purchase_order.order_quantity_pcs if stage in (StageName.fabric_ready, StageName.cutting) and fabric_ready else 0
        if stage == StageName.fabric_ready:
            input_qty = purchase_order.order_quantity_pcs
        completed_qty = purchase_order.order_quantity_pcs if stage == StageName.fabric_ready and fabric_ready else 0
        approved_qty = completed_qty
        moved_to_next_qty = purchase_order.order_quantity_pcs if stage == StageName.fabric_ready and fabric_ready else 0
        pending_qty = 0 if completed_qty else input_qty
        status = StageStatus.completed if completed_qty else StageStatus.blocked
        if stage == StageName.fabric_ready and not fabric_ready:
            status = StageStatus.blocked
        elif stage == StageName.cutting and fabric_ready:
            status = StageStatus.in_progress
        elif stage != StageName.fabric_ready:
            status = StageStatus.not_started

        db.add(
            StageSummary(
                purchase_order_id=purchase_order.id,
                stage=stage,
                sequence=index,
                input_qty=input_qty,
                completed_qty=completed_qty,
                approved_qty=approved_qty,
                moved_to_next_qty=moved_to_next_qty,
                pending_qty=pending_qty,
                status=status,
            )
        )


def _build_design_payload_for_po(
    product_category: str | None,
    custom_name: str,
    custom_photo: str | None,
) -> FabricDesignCreate:
    return FabricDesignCreate(
        category=normalize_category(product_category),
        design_name=custom_name or None,
        image_url=custom_photo,
        is_active=True,
    )
