from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    result = await db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    return list(result.scalars().all())


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
    return purchase_order


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
