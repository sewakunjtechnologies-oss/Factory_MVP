from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Iterable
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.packing_material import PackingMaterialInventory
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageSummary
from app.models.enums import POStatus, StageName
from app.schemas.packing_material import (
    PackingMaterialBackfillSummary,
    PackingMaterialCategoryDemand,
    PackingMaterialCreate,
    PackingMaterialUpdate,
)
from app.services.audit_service import log_audit_event
from app.services.exceptions import DomainError


def recalculate_shortage(row: PackingMaterialInventory) -> None:
    actual_consumed = Decimal(row.actual_consumption_qty or 0)
    if actual_consumed == 0 and Decimal(row.consumed_qty or 0) > 0:
        actual_consumed = Decimal(row.consumed_qty or 0)
    actual_stock = Decimal(row.actual_stock_qty or 0)
    if actual_stock == 0 and Decimal(row.in_stock_qty or 0) > 0:
        actual_stock = Decimal(row.in_stock_qty or 0)
    remaining_required = max(Decimal(row.required_qty or 0) - actual_consumed, Decimal("0"))
    covered = actual_stock + Decimal(row.ordered_qty or 0) + Decimal(row.received_qty or 0)
    row.shortage_qty = max(remaining_required - covered, Decimal("0")).quantize(Decimal("0.001"))
    if row.shortage_qty > 0:
        row.status = "shortage"
    elif actual_consumed >= Decimal(row.required_qty or 0) and Decimal(row.required_qty or 0) > 0:
        row.status = "consumed"
    elif Decimal(row.received_qty or 0) > 0:
        row.status = "received"
    elif Decimal(row.ordered_qty or 0) > 0:
        row.status = "ordered"
    elif Decimal(row.in_stock_qty or 0) > 0:
        row.status = "in_stock"
    else:
        row.status = "unknown"


async def list_packing_materials(
    db: AsyncSession,
    *,
    purchase_order_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[PackingMaterialInventory]:
    stmt = select(PackingMaterialInventory)
    if purchase_order_id is not None:
        stmt = stmt.where(PackingMaterialInventory.purchase_order_id == purchase_order_id)
    if status:
        stmt = stmt.where(PackingMaterialInventory.status == status)
    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(PackingMaterialInventory.po_number).like(pattern),
                func.lower(PackingMaterialInventory.category_name).like(pattern),
                func.lower(PackingMaterialInventory.material_name).like(pattern),
                func.lower(PackingMaterialInventory.material_type).like(pattern),
            )
        )
    result = await db.execute(
        stmt.order_by(
            PackingMaterialInventory.po_number.asc().nullslast(),
            PackingMaterialInventory.category_name.asc(),
            PackingMaterialInventory.material_name.asc(),
        )
    )
    return list(result.scalars().all())


async def get_packing_material(db: AsyncSession, row_id: UUID) -> PackingMaterialInventory:
    row = await db.get(PackingMaterialInventory, row_id)
    if row is None:
        raise DomainError(status_code=404, detail="Packing material row not found")
    return row


async def create_packing_material(
    db: AsyncSession,
    payload: PackingMaterialCreate,
    *,
    actor_id: UUID | None = None,
    actor_role: str | None = None,
) -> PackingMaterialInventory:
    row = PackingMaterialInventory(**payload.model_dump())
    _sync_legacy_and_owner_fields(row)
    recalculate_shortage(row)
    db.add(row)
    await db.flush()
    await log_audit_event(
        db,
        action_type="packing_material_created",
        entity_type="packing_material_inventory",
        entity_id=str(row.id),
        purchase_order_id=row.purchase_order_id,
        performed_by=actor_id,
        role=actor_role,
        new_value_json=_snapshot(row),
    )
    await db.commit()
    await db.refresh(row)
    return row


async def update_packing_material(
    db: AsyncSession,
    row_id: UUID,
    payload: PackingMaterialUpdate,
    *,
    actor_id: UUID | None = None,
    actor_role: str | None = None,
) -> PackingMaterialInventory:
    row = await get_packing_material(db, row_id)
    old = _snapshot(row)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    _sync_legacy_and_owner_fields(row, updated_fields=set(updates))
    if "status" not in updates or any(field.endswith("_qty") for field in updates):
        recalculate_shortage(row)
    await log_audit_event(
        db,
        action_type="packing_material_updated",
        entity_type="packing_material_inventory",
        entity_id=str(row.id),
        purchase_order_id=row.purchase_order_id,
        performed_by=actor_id,
        role=actor_role,
        old_value_json=old,
        new_value_json=_snapshot(row),
    )
    await db.commit()
    await db.refresh(row)
    return row


async def delete_packing_material(
    db: AsyncSession,
    row_id: UUID,
    *,
    actor_id: UUID | None = None,
    actor_role: str | None = None,
) -> None:
    row = await get_packing_material(db, row_id)
    old = _snapshot(row)
    await log_audit_event(
        db,
        action_type="packing_material_deleted",
        entity_type="packing_material_inventory",
        entity_id=str(row.id),
        purchase_order_id=row.purchase_order_id,
        performed_by=actor_id,
        role=actor_role,
        old_value_json=old,
    )
    await db.delete(row)
    await db.commit()


async def backfill_june_packing_materials(db: AsyncSession) -> PackingMaterialBackfillSummary:
    await ensure_packing_material_schema(db)
    result = await db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_number.like("JUNE-%"))
        .options(selectinload(PurchaseOrder.product), selectinload(PurchaseOrder.stage_summaries))
        .order_by(PurchaseOrder.po_number.asc())
    )
    pos = list(result.scalars().all())
    created = 0
    updated = 0
    existing = await _existing_by_key(db)
    for po in pos:
        category_name = po.product.product_name if po.product else po.design_name_snapshot or po.po_number
        consumed_pieces = _packing_consumed_pieces(po)
        shortage_like = po.status in {POStatus.shortage, POStatus.fabric_check_pending, POStatus.draft}
        specs = _requirements_for_po(po)
        generated_rows = {
            material_row.material_name: material_row
            for material_row in existing.values()
            if material_row.purchase_order_id == po.id
            and (material_row.notes or "").startswith("Generated from June PO packing requirement")
        }
        for obsolete_name, obsolete_row in generated_rows.items():
            if obsolete_name not in {str(spec["material_name"]) for spec in specs}:
                await db.delete(obsolete_row)
        for spec in specs:
            consumed_qty = _consumed_for_material(spec, consumed_pieces)
            remaining_required = max(spec["required_qty"] - consumed_qty, Decimal("0"))
            if shortage_like:
                in_stock_qty = Decimal("0")
                ordered_qty = remaining_required
                received_qty = Decimal("0")
                supplier = "Packing supplier follow-up"
            else:
                in_stock_qty = remaining_required
                ordered_qty = Decimal("0")
                received_qty = Decimal("0")
                supplier = None
            key = (po.id, spec["material_name"])
            row = existing.get(key)
            if row is None:
                row = PackingMaterialInventory(
                    purchase_order_id=po.id,
                    po_number=po.po_number,
                    category_name=category_name,
                    material_name=spec["material_name"],
                    material_type=spec["material_type"],
                    unit=spec["unit"],
                    required_qty=spec["required_qty"],
                    in_stock_qty=in_stock_qty,
                    ordered_qty=ordered_qty,
                    received_qty=received_qty,
                    consumed_qty=consumed_qty,
                    printed_consumption_qty=spec["required_qty"],
                    actual_consumption_qty=consumed_qty,
                    printed_stock_qty=in_stock_qty,
                    actual_stock_qty=in_stock_qty,
                    supplier_name=supplier,
                    notes="Generated from June PO packing requirement.",
                )
                db.add(row)
                created += 1
            else:
                row.po_number = po.po_number
                row.category_name = category_name
                row.material_type = spec["material_type"]
                row.unit = spec["unit"]
                row.required_qty = spec["required_qty"]
                row.consumed_qty = consumed_qty
                row.printed_consumption_qty = spec["required_qty"]
                row.actual_consumption_qty = consumed_qty
                if row.notes is None or "Generated from June PO packing requirement" in row.notes:
                    row.in_stock_qty = in_stock_qty
                    row.ordered_qty = ordered_qty
                    row.received_qty = received_qty
                    row.printed_stock_qty = in_stock_qty
                    row.actual_stock_qty = in_stock_qty
                    row.supplier_name = supplier
                    row.notes = "Generated from June PO packing requirement."
                updated += 1
            recalculate_shortage(row)
    await db.commit()
    return PackingMaterialBackfillSummary(
        rows_created=created,
        rows_updated=updated,
        purchase_orders_scanned=len(pos),
    )


async def list_category_demand(db: AsyncSession) -> list[PackingMaterialCategoryDemand]:
    result = await db.execute(select(PurchaseOrder).options(selectinload(PurchaseOrder.product)))
    grouped: dict[str, dict[str, int | str]] = {}
    for po in result.scalars().all():
        label, rule = _packing_rule_for_po(po)
        bucket = grouped.setdefault(label, {"order_count": 0, "total_pieces": 0, "material_rule": rule})
        bucket["order_count"] = int(bucket["order_count"]) + 1
        bucket["total_pieces"] = int(bucket["total_pieces"]) + int(po.order_quantity_pcs or 0)
        bucket["material_rule"] = rule
    return [
        PackingMaterialCategoryDemand(
            category=category,
            order_count=int(values["order_count"]),
            total_pieces=int(values["total_pieces"]),
            material_rule=str(values["material_rule"]),
        )
        for category, values in sorted(grouped.items(), key=lambda item: int(item[1]["total_pieces"]), reverse=True)
    ]


async def _existing_by_key(db: AsyncSession) -> dict[tuple[UUID, str], PackingMaterialInventory]:
    rows = (await db.execute(select(PackingMaterialInventory))).scalars().all()
    return {
        (row.purchase_order_id, row.material_name): row
        for row in rows
        if row.purchase_order_id is not None
    }


def _requirements_for_po(po: PurchaseOrder) -> list[dict[str, Decimal | str]]:
    qty = Decimal(po.order_quantity_pcs)
    _, rule = _packing_rule_for_po(po)
    material_names = {
        "tag": ("Tag",),
        "insert_stiffener_bag": ("Insert", "Stiffener", "Bag"),
        "header": ("Header",),
    }.get(rule, ("Tag",))
    return [
        {"material_name": name, "material_type": name.lower().replace(" ", "_"), "unit": "pcs", "required_qty": qty}
        for name in material_names
    ]


def _packing_rule_for_po(po: PurchaseOrder) -> tuple[str, str]:
    raw_name = " ".join(
        value
        for value in (
            po.product.product_name if po.product else None,
            po.design_name_snapshot,
            po.notes,
        )
        if value
    )
    normalized = raw_name.lower().replace("_", " ")
    compact = normalized.replace("-", " ")
    if "499" in compact:
        return "499", "insert_stiffener_bag"
    if "399" in compact:
        return "399", "header"
    if "299" in compact:
        return "299", "header"
    if "199" in compact and ("pkd" in compact or "packed" in compact):
        return "199 PKD", "insert_stiffener_bag"
    if "199" in compact and ("1+1" in compact or "1 + 1" in compact):
        return "199 1+1", "header"
    if "199" in compact and ("without pillow" in compact or "without-pillow" in normalized):
        return "199 without pillow", "tag"
    if "199" in compact:
        return "199", "header"
    if "109" in compact:
        return "109", "tag"
    if "69" in compact:
        return "69 pillow", "tag"
    return "Other", "tag"


def _packing_consumed_pieces(po: PurchaseOrder) -> int:
    packing = next((stage for stage in po.stage_summaries if stage.stage == StageName.packing), None)
    dispatch = next((stage for stage in po.stage_summaries if stage.stage == StageName.dispatch), None)
    return max(
        int(packing.approved_qty or 0) if packing else 0,
        int(dispatch.completed_qty or 0) if dispatch else 0,
    )


def _consumed_for_material(spec: dict[str, Decimal | str], consumed_pieces: int) -> Decimal:
    pieces = Decimal(consumed_pieces)
    return min(pieces, Decimal(spec["required_qty"]))


def _sync_legacy_and_owner_fields(row: PackingMaterialInventory, updated_fields: set[str] | None = None) -> None:
    updated_fields = updated_fields or set()
    if not updated_fields:
        if Decimal(row.actual_stock_qty or 0) == 0 and Decimal(row.in_stock_qty or 0) > 0:
            row.actual_stock_qty = Decimal(row.in_stock_qty or 0)
        if Decimal(row.actual_consumption_qty or 0) == 0 and Decimal(row.consumed_qty or 0) > 0:
            row.actual_consumption_qty = Decimal(row.consumed_qty or 0)
    if "actual_stock_qty" in updated_fields:
        row.in_stock_qty = Decimal(row.actual_stock_qty or 0)
    elif "in_stock_qty" in updated_fields:
        row.actual_stock_qty = Decimal(row.in_stock_qty or 0)
    if "actual_consumption_qty" in updated_fields:
        row.consumed_qty = Decimal(row.actual_consumption_qty or 0)
    elif "consumed_qty" in updated_fields:
        row.actual_consumption_qty = Decimal(row.consumed_qty or 0)
    if Decimal(row.printed_stock_qty or 0) == 0 and Decimal(row.in_stock_qty or 0) > 0:
        row.printed_stock_qty = Decimal(row.in_stock_qty or 0)
    if Decimal(row.printed_consumption_qty or 0) == 0 and Decimal(row.required_qty or 0) > 0:
        row.printed_consumption_qty = Decimal(row.required_qty or 0)


def _ceil(value: Decimal) -> Decimal:
    return value.to_integral_value(rounding=ROUND_CEILING)


def _snapshot(row: PackingMaterialInventory) -> dict:
    return {
        "po_number": row.po_number,
        "category_name": row.category_name,
        "material_name": row.material_name,
        "required_qty": str(row.required_qty),
        "in_stock_qty": str(row.in_stock_qty),
        "ordered_qty": str(row.ordered_qty),
        "received_qty": str(row.received_qty),
        "consumed_qty": str(row.consumed_qty),
        "printed_consumption_qty": str(row.printed_consumption_qty),
        "actual_consumption_qty": str(row.actual_consumption_qty),
        "printed_stock_qty": str(row.printed_stock_qty),
        "actual_stock_qty": str(row.actual_stock_qty),
        "shortage_qty": str(row.shortage_qty),
        "status": row.status,
    }


async def ensure_packing_material_schema(db: AsyncSession) -> None:
    """Add additive packing-material columns for existing demo databases."""
    dialect = db.bind.dialect.name if db.bind is not None else ""
    columns = {
        "printed_consumption_qty": "NUMERIC(14, 3) NOT NULL DEFAULT 0",
        "actual_consumption_qty": "NUMERIC(14, 3) NOT NULL DEFAULT 0",
        "printed_stock_qty": "NUMERIC(14, 3) NOT NULL DEFAULT 0",
        "actual_stock_qty": "NUMERIC(14, 3) NOT NULL DEFAULT 0",
    }
    if dialect == "sqlite":
        result = await db.execute(text("PRAGMA table_info(packing_material_inventory)"))
        existing = {str(row[1]) for row in result.fetchall()}
        for name, definition in columns.items():
            if name not in existing:
                await db.execute(text(f"ALTER TABLE packing_material_inventory ADD COLUMN {name} {definition}"))
        await db.commit()
        return
    for name, definition in columns.items():
        await db.execute(text(f"ALTER TABLE packing_material_inventory ADD COLUMN IF NOT EXISTS {name} {definition}"))
    await db.commit()
