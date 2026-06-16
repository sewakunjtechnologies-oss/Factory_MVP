from __future__ import annotations

import asyncio
import pathlib
import sys
from datetime import date
from decimal import Decimal

SCRIPT_PATH = pathlib.Path(__file__).resolve()
BACKEND = SCRIPT_PATH.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, create_all_tables
from app.models.dispatch import DispatchLoad
from app.models.enums import DispatchCostType, POStatus, StageName, StageStatus
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageSummary
from app.schemas.dispatch import DispatchLoadCreate
from app.services.dispatch_engine import create_dispatch_load
from app.services.packing_material_service import backfill_june_packing_materials, ensure_packing_material_schema


OWNER_DISPATCH_UPDATES = {
    "JUNE-004": 3380,
    "JUNE-005": 9000,
}


async def main() -> None:
    await create_all_tables()
    async with AsyncSessionLocal() as db:
        await ensure_packing_material_schema(db)
        summary = await backfill_june_packing_materials(db)
        applied = []
        for po_number, dispatched_qty in OWNER_DISPATCH_UPDATES.items():
            po = await _load_po(db, po_number)
            if po is None:
                print(f"Skipped {po_number}: PO not found")
                continue
            await _prepare_partial_dispatch_stages(db, po, dispatched_qty)
            await db.execute(
                delete(DispatchLoad).where(
                    DispatchLoad.purchase_order_id == po.id,
                    DispatchLoad.load_number == f"OWNER-{po_number}-PARTIAL",
                )
            )
            await db.flush()
            await create_dispatch_load(
                db,
                DispatchLoadCreate(
                    purchase_order_id=po.id,
                    load_number=f"OWNER-{po_number}-PARTIAL",
                    shipped_qty=dispatched_qty,
                    vehicle_type="Owner update",
                    actual_loaded_pieces=dispatched_qty,
                    cost_type=DispatchCostType.manual,
                    manual_cost=Decimal("0"),
                    shipped_at=date(2026, 6, 5),
                    transporter_name="Owner status update",
                    document_status="complete",
                    invoice_uploaded=True,
                    packing_list_uploaded=True,
                    eway_bill_uploaded=True,
                    transporter_confirmation=True,
                    buyer_dispatch_approval=True,
                    remarks="OWNER_JUNE_UPDATE",
                ),
            )
            applied.append(f"{po_number}: {dispatched_qty} pcs")
        print("Owner June updates applied.")
        print(f"Packing material backfill: {summary.purchase_orders_scanned} POs, {summary.rows_created} created, {summary.rows_updated} updated.")
        print("Partial dispatch updates:")
        for item in applied:
            print(f"- {item}")


async def _load_po(db, po_number: str) -> PurchaseOrder | None:
    result = await db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_number == po_number)
        .options(selectinload(PurchaseOrder.stage_summaries))
    )
    return result.scalar_one_or_none()


async def _prepare_partial_dispatch_stages(db, po: PurchaseOrder, dispatched_qty: int) -> None:
    stages = {
        row.stage: row
        for row in po.stage_summaries
    }
    ordered_stages = (
        StageName.fabric_ready,
        StageName.cutting,
        StageName.stitching,
        StageName.size_inspection,
        StageName.quality_check,
        StageName.packing,
        StageName.dispatch,
    )
    for sequence, stage_name in enumerate(ordered_stages):
        row = stages.get(stage_name)
        if row is None:
            row = StageSummary(purchase_order_id=po.id, stage=stage_name, sequence=sequence)
            db.add(row)
            stages[stage_name] = row
        row.sequence = sequence
        if stage_name == StageName.dispatch:
            row.input_qty = max(row.input_qty or 0, dispatched_qty)
            row.completed_qty = 0
            row.approved_qty = 0
            row.pending_qty = dispatched_qty
            row.status = StageStatus.in_progress
        elif stage_name in {StageName.packing, StageName.quality_check, StageName.size_inspection, StageName.stitching, StageName.cutting}:
            row.input_qty = max(row.input_qty or 0, po.order_quantity_pcs)
            row.completed_qty = max(row.completed_qty or 0, dispatched_qty)
            row.approved_qty = max(row.approved_qty or 0, dispatched_qty)
            row.moved_to_next_qty = max(row.moved_to_next_qty or 0, dispatched_qty)
            row.pending_qty = max(po.order_quantity_pcs - row.completed_qty, 0)
            row.status = StageStatus.in_progress if row.pending_qty else StageStatus.completed
        else:
            row.input_qty = po.order_quantity_pcs
            row.completed_qty = po.order_quantity_pcs
            row.approved_qty = po.order_quantity_pcs
            row.moved_to_next_qty = po.order_quantity_pcs
            row.pending_qty = 0
            row.status = StageStatus.completed
    po.status = POStatus.partially_dispatched


if __name__ == "__main__":
    asyncio.run(main())
