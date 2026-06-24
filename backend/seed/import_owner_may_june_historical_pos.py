from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.dispatch import DispatchLoad
from app.models.enums import DispatchCostType, PODesignStatus, POStatus
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.services.audit_service import log_audit_event

MAY_BATCH = "OWNER_MAY_2026"
JUNE_BATCH = "OWNER_JUNE_2026"


@dataclass(frozen=True)
class ImportRow:
    batch: str
    source_row: int
    po_number: str
    category_group: str
    category_text: str
    quantity: int
    delivery_date: date


MAY_ROWS = [
    ("109 MRP", "ASSORTED", 8000),
    ("109 MRP", "FROSTED-LEAF", 4000),
    ("109 MRP", "RETRO-BLOCK", 5000),
    ("109 MRP", "GARDEN-BLOOM", 4000),
    ("109 MRP", "BEIGE-DMASK", 9000),
    ("109 MRP", "MINI-FERN", 5000),
    ("109 MRP", "BRN-BRICK", 5140),
    ("199-PKD", "MISTY", 7000),
    ("199-PKD", "TEAL", 4000),
    ("199-PKD", "CHARCOAL", 5000),
    ("299", "SAGE-GRID", 1002),
    ("299", "EARTHY-ABSTRACT", 5580),
    ("299", "MODERN GEO", 3000),
    ("399", "JAIPURI", 5110),
    ("399", "GOLD STEAM", 2000),
    ("399", "MODERN STONE", 2000),
    ("499", "FITTED", 4000),
    ("499", "PREMIUM", 1400),
    ("499", "WHITE BEAUTY", 4400),
]

JUNE_ROWS = [
    ("69", "69-JAI MICRO-BLUE-50X75-TIR-12-26", 6996),
    ("69", "69-JAI MICRO-WINE-50X75-TIR-12-26", 6996),
    ("69", "69-JAI MICRO-GREY-50X75-TIR-12-26", 6996),
    ("69", "69-MICRO-LIGHT FLORAL-50X75-TIR-12-26", 14004),
    ("69", "69-MICRO-DARK FLORAL-50X75-TIR-12-26", 20004),
    ("99", "99-PLR-300-BLK-STP-111X213-PL-TIR-10-26", 7000),
    ("109", "109-BLUGRN-FLORA-140X215-PL-TIR-10-26", 8000),
    ("109", "109-ORNG-HIBISCUS-140X215-PL-TIR-10-26", 8500),
    ("109", "109-BRN-BRICK-140X215-PL-TIR-10-26", 9000),
    ("109", "109-BEIGE-DMASK-140X215-PL-TIR-10-26", 8000),
    ("109", "109-GARDEN-BLOOM-140X215-PL-TIR-10-26", 5000),
    ("199", "199-KIDS-CARTOON-140X215-PL-TIR-10-26", 800),
    ("199", "199-PACKEDWPC-TEAL-140X215-MC-TIR-6-25", 4000),
    ("199", "199-PACKEDWPC-MISTY-140X215-MC-TIR-6-25", 4500),
    ("199", "199-PACKEDWPC-MISTY-140X215-MC-TIR-6-25", 3000),
    ("199", "199-BLACK&WHITE-140X215-PL-TIR-10-25", 8000),
    ("199", "199-BLACK&WHITE-140X215-PL-TIR-10-25", 3000),
    ("199", "199-CHARCOAL-FOLK-140X215-PL-TIR-10-26", 4000),
    ("199", "199-CHARCOAL-FOLK-140X215-PL-TIR-10-26", 6000),
    ("199", "199-CHARCOAL-FOLK-140X215-PL-TIR-10-26", 3000),
    ("299", "299-SAGE-GRID-BOTANC-215X225-MC-TIR-6-26", 2802),
    ("299", "299-SAGE-GRID-BOTANC-215X225-MC-TIR-6-26", 4338),
    ("299", "299-MODERN-GEO-215X225-MC-TIR-6-26", 6498),
    ("299", "299-MODERN-GEO-215X225-MC-TIR-6-26", 1800),
    ("299", "299-VINTAGE-PAISLEY-215X225-MC-TIR-6-26", 1998),
    ("299", "299-VINTAGE-PAISLEY-215X225-MC-TIR-6-26", 2370),
    ("299", "299-EARTHY-ABSTRACT-215X225-MC-TIR-6-26", 4002),
    ("299", "299-MIDNIGHT-FLORA-215X225-MC-TIR-6-26", 4998),
    ("299", "299-MIDNIGHT-FLORA-215X225-MC-TIR-6-26", 1800),
    ("399", "399-MODERN-STONE-220X230-MC-TIR-05-26", 3000),
    ("399", "399-GOLD-STEM-220X230-MC-TIR-05-26", 8000),
    ("399", "399-JAIPURI-220X240-MC-TIR-05-26", 7000),
    ("499", "499-PREMIUM-230X270-MC-TIR-S-26", 2000),
    ("499", "499-FITTED-180X190-MC-TIR-S-26", 1000),
    ("499", "499-FITTED-180X190-MC-TIR-S-26", 3000),
    ("499", "499-SOLID-PRINT-EMB-230X265-MC-TIR-S-26", 3500),
    ("499", "499-WHITEREALITY-230X274-MC-TIR-S-26", 6000),
]


def build_rows() -> list[ImportRow]:
    rows: list[ImportRow] = []
    for idx, (group, text, qty) in enumerate(MAY_ROWS, start=1):
        rows.append(ImportRow(MAY_BATCH, idx, f"MAY-2026-{idx:03d}", group, text, qty, date(2026, 5, 31)))
    for idx, (group, text, qty) in enumerate(JUNE_ROWS, start=1):
        rows.append(ImportRow(JUNE_BATCH, idx, f"JUNE-2026-{idx:03d}", group, text, qty, date(2026, 6, 30)))
    return rows


def marker(batch: str, source_row: int) -> str:
    return f"Historical Import | batch={batch} | source_row={source_row}"


def mrp_from_group(group: str) -> Decimal | None:
    match = re.search(r"\d+", group)
    return Decimal(match.group(0)) if match else None


async def get_or_create_product(db: AsyncSession, row: ImportRow) -> Product:
    result = await db.execute(
        select(Product).where(Product.product_name == row.category_text, Product.product_category == "historical_import")
    )
    product = result.scalar_one_or_none()
    if product is not None:
        return product
    product = Product(
        product_name=row.category_text,
        product_category="historical_import",
        size="Historical",
        design=row.category_text,
        color="Imported",
        fabric_type=row.category_group,
        gsm=Decimal("0"),
        width=Decimal("0"),
        per_piece_fabric_usage_m=Decimal("0"),
        wastage_percent=Decimal("0"),
    )
    db.add(product)
    await db.flush()
    db.add(
        ProductFabricLine(
            product_id=product.id,
            fabric_code=row.category_text,
            pieces=row.quantity,
            pieces_in_stock=0,
            pieces_short=0,
            stock_status="historical",
            per_piece_meters=Decimal("0"),
            stock_meters=Decimal("0"),
            dispatch="done",
            notes=f"Created for {row.batch} historical import.",
        )
    )
    await db.flush()
    return product


async def upsert_row(db: AsyncSession, row: ImportRow) -> None:
    product = await get_or_create_product(db, row)
    note_marker = marker(row.batch, row.source_row)
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == row.po_number))
    po = result.scalar_one_or_none()
    is_new = po is None
    notes = f"{note_marker} | source_text={row.category_text} | editable=true | import_notes=No active stock impact."
    if po is None:
        po = PurchaseOrder(
            po_number=row.po_number,
            product_id=product.id,
            order_quantity_pcs=row.quantity,
            mrp=mrp_from_group(row.category_group),
            selling_price=None,
            order_date=date(2026, 5 if row.batch == MAY_BATCH else 6, 1),
            promise_delivery_date=row.delivery_date,
            actual_delivery_date=row.delivery_date,
            status=POStatus.completed,
            notes=notes,
            design_name_snapshot=row.category_text,
            design_code_snapshot=row.category_text[:30],
            design_status=PODesignStatus.custom_design,
            priority_level="normal",
        )
        db.add(po)
        await db.flush()
    else:
        po.product_id = product.id
        po.order_quantity_pcs = row.quantity
        po.promise_delivery_date = row.delivery_date
        po.actual_delivery_date = row.delivery_date
        po.status = POStatus.completed
        po.notes = notes
        po.design_name_snapshot = row.category_text
        po.design_code_snapshot = row.category_text[:30]
        await db.flush()

    load_result = await db.execute(select(DispatchLoad).where(DispatchLoad.purchase_order_id == po.id, DispatchLoad.load_number == f"{row.po_number}-HISTORICAL"))
    load = load_result.scalar_one_or_none()
    if load is None:
        db.add(
            DispatchLoad(
                purchase_order_id=po.id,
                load_number=f"{row.po_number}-HISTORICAL",
                shipped_qty=row.quantity,
                actual_loaded_pieces=row.quantity,
                cost_type=DispatchCostType.manual,
                manual_cost=Decimal("0"),
                dispatch_cost=Decimal("0"),
                cost_per_piece=Decimal("0"),
                shipped_at=row.delivery_date,
                document_status="historical",
                invoice_uploaded=True,
                packing_list_uploaded=True,
                transporter_confirmation=True,
                remarks="Historical import dispatch record; does not consume current stock.",
            )
        )
    else:
        load.shipped_qty = row.quantity
        load.actual_loaded_pieces = row.quantity
        load.shipped_at = row.delivery_date
        load.remarks = "Historical import dispatch record; does not consume current stock."

    await log_audit_event(
        db,
        action_type="historical_po_imported" if is_new else "historical_po_import_updated",
        entity_type="purchase_order",
        entity_id=str(po.id),
        purchase_order_id=po.id,
        role="system",
        new_value_json={"batch": row.batch, "source_row": row.source_row, "quantity": row.quantity, "category_text": row.category_text},
    )


async def apply_rows(rows: list[ImportRow]) -> None:
    async with AsyncSessionLocal() as db:
        for row in rows:
            await upsert_row(db, row)
        await db.commit()
    print(f"Applied {len(rows)} historical POs.")


async def rollback_batch(batch: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.notes.ilike(f"%batch={batch}%")))
        rows = result.scalars().all()
        for po in rows:
            await db.delete(po)
        await db.commit()
    print(f"Rolled back {len(rows)} records from {batch}.")


def print_preview(rows: list[ImportRow]) -> None:
    may = [row for row in rows if row.batch == MAY_BATCH]
    june = [row for row in rows if row.batch == JUNE_BATCH]
    duplicates: dict[str, int] = {}
    for row in june:
        duplicates[row.category_text] = duplicates.get(row.category_text, 0) + 1
    duplicated = {key: value for key, value in duplicates.items() if value > 1}
    print("Historical PO import preview")
    print(f"May: {len(may)} rows, total {sum(row.quantity for row in may):,} pcs")
    print(f"June: {len(june)} rows, total {sum(row.quantity for row in june):,} pcs")
    print("Duplicate June category rows:")
    for key, count in duplicated.items():
        print(f"  - {key}: {count} rows")
    print("\nRows:")
    for row in rows:
        print(f"{row.po_number} | {row.batch} row {row.source_row:02d} | {row.category_text} | {row.quantity:,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import owner May/June historical dispatched PO records.")
    parser.add_argument("--preview", action="store_true", help="Print parsed rows without changing the database.")
    parser.add_argument("--apply", action="store_true", help="Insert/update historical rows.")
    parser.add_argument("--rollback-batch", choices=[MAY_BATCH, JUNE_BATCH], help="Delete only rows from one import batch.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    rows = build_rows()
    if args.rollback_batch:
        await rollback_batch(args.rollback_batch)
        return
    if args.apply:
        await apply_rows(rows)
        return
    print_preview(rows)


if __name__ == "__main__":
    asyncio.run(main())
