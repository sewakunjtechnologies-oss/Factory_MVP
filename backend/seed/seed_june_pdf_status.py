from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, create_all_tables
from app.core.security import hash_password
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.contractor import Contractor
from app.models.dispatch import DispatchLoad
from app.models.enums import (
    AlertPriority,
    AlertType,
    ContractorType,
    DispatchCostType,
    FabricMillOrderStatus,
    FabricPlanStatus,
    PODesignStatus,
    POStatus,
    ReceiptStatus,
    StageName,
    StageStatus,
    UserRole,
)
from app.models.fabric import (
    DebitNote,
    FabricInventory,
    FabricIssueToCutting,
    FabricMillOrder,
    FabricPlan,
    FabricReceipt,
    MillDeliveryLot,
    MillFollowUp,
    MillOrderSplit,
    MillOrderStatusHistory,
    SupplierReturn,
)
from app.models.fabric_meter_receipt import FabricMeterReceipt
from app.models.mill_requirement import MillOrderRequirement, MillOrderRequirementStatus
from app.models.notification import Notification
from app.models.pieces_receipt import PiecesReceipt
from app.models.po_draft import PODraft
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import Reminder, ReminderPriority, ReminderStatus, ReminderType
from app.models.stage import (
    ContractorAllocation,
    CuttingAnalysis,
    MillWastageRecord,
    PackingOutput,
    QualityFailure,
    StageCostEntry,
    StageProgressEntry,
    StageSummary,
)
from app.models.user import User
from app.models.vehicle import Vehicle


SEED_MARKER = "JUNE_PDF_STATUS_2026"
SEED_ORDER_DATE = date(2026, 6, 2)
SEED_DEADLINE = date(2026, 6, 30)
PIECES_PER_BALE = 100


@dataclass(frozen=True)
class JuneRow:
    category: str
    qty: int
    weight_per_piece: str
    volume_metric: str
    status_text: str


JUNE_ROWS: list[JuneRow] = [
    JuneRow("69-JAI MICRO-BLUE-50X75-TIR-12-26", 6996, "60gm", "0.0005", "Fabric Recieved of PO Qty"),
    JuneRow("69-JAI MICRO-WINE-50X75-TIR-12-26", 6996, "60gm", "0.0005", "Fabric Recieved of PO Qty"),
    JuneRow("69-JAI MICRO-GREY-50X75-TIR-12-26", 6996, "60gm", "0.0005", "Fabric Recieved of PO Qty"),
    JuneRow("69-MICRO-LIGHT FLORAL-50X75-TIR-12-26", 14004, "60gm", "0.0005", "Fabric Recieved of PO Qty"),
    JuneRow("69-MICRO-DARK FLORAL-50X75-TIR-12-26", 20004, "60gm", "0.0005", "Fabric Recieved of PO Qty"),
    JuneRow("99-PLR-300-BLK-STP-111X213-PL-TIR-10-26", 7000, "60gm", "N/A", "Fabric Orderd But not received"),
    JuneRow("109-BLUGRN-FLORA-140X215-PL-TIR-10-26", 8000, "300gm", "0.001493", "Fabric Recieved of PO Qty"),
    JuneRow("109-ORNG-HIBISCUS-140X215-PL-TIR-10-26", 8500, "300gm", "0.001493", "Fabric Recieved of PO Qty"),
    JuneRow("109-BRN-BRICK-140X215-PL-TIR-10-26", 9000, "300gm", "0.001493", "Fabric Recieved of PO Qty"),
    JuneRow("109-BEIGE-DMASK-140X215-PL-TIR-10-26", 8000, "300gm", "0.001493", "Fabric Recieved of PO Qty"),
    JuneRow("109-GARDEN-BLOOM-140X215-PL-TIR-10-26", 5000, "300gm", "0.001493", "Fabric Orderd But not received"),
    JuneRow("199-KIDS-CARTOON-140X215-PL-TIR-10-26", 800, "400gm", "", "Not In Stock; order alert"),
    JuneRow("199-PACKEDWPC-TEAL-140X215-MC-TIR-6-25", 4000, "400gm", "", "Fabric Recieved of PO Qty"),
    JuneRow("199-PACKEDWPC-MISTY-140X215-MC-TIR-6-25", 4500, "400gm", "", "Fabric Recieved of PO Qty"),
    JuneRow("199-PACKEDWPC-MISTY-140X215-MC-TIR-6-25", 3000, "400gm", "", "Today Dispatch"),
    JuneRow("199-BLACK&WHITE-140X215-PL-TIR-10-25", 8000, "400gm", "", "Fabric Orderd But not received"),
    JuneRow("199-BLACK&WHITE-140X215-PL-TIR-10-25", 3000, "400gm", "", "Fabric Recieved of PO Qty"),
    JuneRow("199-CHARCOAL-FOLK-140X215-PL-TIR-10-26", 4000, "400gm", "", "Fabric Recieved of PO Qty"),
    JuneRow("199-CHARCOAL-FOLK-140X215-PL-TIR-10-26", 6000, "400gm", "", "Fabric Orderd But not received"),
    JuneRow("199-CHARCOAL-FOLK-140X215-PL-TIR-10-26", 3000, "400gm", "", "Fabric Recieved of PO Qty"),
    JuneRow("299-SAGE-GRID-BOTANC-215X225-MC-TIR-6-26", 2802, "700gm", "0.0027", ""),
    JuneRow("299-SAGE-GRID-BOTANC-215X225-MC-TIR-6-26", 4338, "700gm", "0.0027", "Fabric Orderd But not received"),
    JuneRow("299-MODERN-GEO-215X225-MC-TIR-6-26", 6498, "700gm", "0.0027", "2000pcs in stock and balance fabric orderd"),
    JuneRow("299-MODERN-GEO-215X225-MC-TIR-6-26", 1800, "700gm", "0.0027", "2000pcs in stock and balance fabric orderd"),
    JuneRow("299-VINTAGE-PAISLEY-215X225-MC-TIR-6-26", 1998, "700gm", "0.0027", "Fabric Orderd But not received"),
    JuneRow("299-VINTAGE-PAISLEY-215X225-MC-TIR-6-26", 2370, "700gm", "0.0027", "Fabric Orderd But not received"),
    JuneRow("299-EARTHY-ABSTRACT-215X225-MC-TIR-6-26", 4002, "700gm", "0.0027", "1000pcs in stock balance Fabric ordered"),
    JuneRow("299-MIDNIGHT-FLORA-215X225-MC-TIR-6-26", 4998, "700gm", "0.0027", "Fabric Orderd But not received"),
    JuneRow("299-MIDNIGHT-FLORA-215X225-MC-TIR-6-26", 1800, "700gm", "0.0027", "Fabric Orderd But not received"),
    JuneRow("399-MODERN-STONE-220X230-MC-TIR-05-26", 3000, "1kg", "0.0035", "Stitiched"),
    JuneRow("399-GOLD-STEM-220X230-MC-TIR-05-26", 8000, "1kg", "0.0035", "4000pcs dispatched;Balance Fabric received"),
    JuneRow("399-JAIPURI-220X240-MC-TIR-05-26", 7000, "1kg", "0.0035", "4000pcs dispatched;Balance Fabric received"),
    JuneRow("499-PREMIUM-230X270-MC-TIR-5-26", 2000, "1kg", "0.0084", "ready"),
    JuneRow("499-FITTED-180X190-MC-TIR-5-26", 1000, "1kg", "0.0084", "In Stitching"),
    JuneRow("499-FITTED-180X190-MC-TIR-5-26", 3000, "1kg", "0.0084", "In Stitching"),
    JuneRow("499-SOLID-PRINT-EMB-230X265-MC-TIR-5-26", 3500, "1kg", "0.0084", "1200pcs Ready; balance Fabric required"),
    JuneRow("499-WHITEBEAUTY-230X274-MC-TIR-5-26", 6000, "1kg", "0.0084", "3000 Dispatched"),
]


VEHICLE_ROWS: list[tuple[str, Decimal, Decimal, str]] = [
    ("14 feet", Decimal("14"), Decimal("3500"), "vehicleData.pdf: CBM 14, weight 3500 kg"),
    ("15 feet", Decimal("16"), Decimal("4000"), "Owner-requested 15 feet option; estimated between 14 feet and 17 feet capacities"),
    ("17 feet", Decimal("25"), Decimal("5500"), "vehicleData.pdf: CBM range 20-25, weight 5500 kg; using max CBM"),
    ("20 feet", Decimal("30"), Decimal("5500"), "vehicleData.pdf: CBM range 28-30, weight 5500 kg; using max CBM"),
    ("24 feet", Decimal("35"), Decimal("9000"), "vehicleData.pdf: CBM range 30-35, weight 9000 kg; using max CBM"),
    ("26 feet", Decimal("45"), Decimal("10000"), "vehicleData.pdf: CBM range 40-45, weight 10000 kg; using max CBM"),
]


def dec(value: Any) -> Decimal:
    return Decimal(str(value))


async def main() -> None:
    await create_all_tables()
    async with AsyncSessionLocal() as db:
        owner = await _ensure_demo_users(db)
        await _clear_operational_data(db)
        await _seed_contractors(db)
        await _seed_vehicles(db)
        await _seed_inventory(db)
        stats = await _seed_pos(db, owner.id)
        await db.commit()
        print("June PDF status seed completed.")
        print(f"POs created: {stats['pos_created']}")
        print(f"Products/categories created: {stats['products_created']}")
        print(f"Fabric received / ready POs: {stats['fabric_ready']}")
        print(f"Fabric ordered / shortage POs: {stats['shortage']}")
        print(f"Mill orders created: {stats['mill_orders']}")
        print(f"Dispatch loads created: {stats['dispatch_loads']}")
        print(f"Vehicles created from vehicleData.pdf: {len(VEHICLE_ROWS)}")
        print("Visible site data now matches June POs Status.pdf rows only.")


async def _ensure_demo_users(db: AsyncSession) -> User:
    owner = await _get_or_create_user(db, "Factory Owner", "owner@factorydemo.com", "Owner@123", UserRole.owner)
    await _get_or_create_user(db, "Production Manager", "manager@factorydemo.com", "Manager@123", UserRole.manager)
    await db.flush()
    return owner


async def _get_or_create_user(db: AsyncSession, name: str, email: str, password: str, role: UserRole) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        user.full_name = name
        user.role = role
        user.is_active = True
        return user
    user = User(full_name=name, email=email, password_hash=hash_password(password), role=role, is_active=True)
    db.add(user)
    await db.flush()
    return user


async def _clear_operational_data(db: AsyncSession) -> None:
    # Preserve users. Everything else below is factory demo/workflow data that
    # must be replaced by the latest June status sheet.
    for model in (
        StageProgressEntry,
        QualityFailure,
        ContractorAllocation,
        StageSummary,
        CuttingAnalysis,
        MillWastageRecord,
        PackingOutput,
        StageCostEntry,
        DispatchLoad,
        SupplierReturn,
        DebitNote,
        FabricIssueToCutting,
        MillOrderStatusHistory,
        MillDeliveryLot,
        MillFollowUp,
        MillOrderSplit,
        FabricMillOrder,
        FabricReceipt,
        MillOrderRequirement,
        FabricPlan,
        FabricMeterReceipt,
        PiecesReceipt,
        Alert,
        Reminder,
        Notification,
        AuditLog,
        PODraft,
        ProductFabricLine,
        PurchaseOrder,
        Product,
        FabricInventory,
        Contractor,
        Vehicle,
    ):
        await db.execute(delete(model))
    await db.flush()


async def _seed_contractors(db: AsyncSession) -> None:
    contractors = [
        ("Shivam Mill", ContractorType.mill),
        ("Krishna Mill", ContractorType.mill),
        ("XYZ Mill", ContractorType.mill),
        ("Cutting Contractor A", ContractorType.cutting),
        ("Kumar Factors", ContractorType.stitching),
        ("Packing Team A", ContractorType.packing),
        ("Haryana Transport", ContractorType.transport),
    ]
    for name, contractor_type in contractors:
        db.add(Contractor(name=name, contractor_type=contractor_type, is_active=True))
    await db.flush()


async def _seed_vehicles(db: AsyncSession) -> None:
    for name, cbm, weight, notes in VEHICLE_ROWS:
        db.add(
            Vehicle(
                name=name,
                registration_number=None,
                cbm_capacity=cbm,
                max_weight_kg=weight,
                notes=notes,
                is_active=True,
            )
        )
    await db.flush()


async def _seed_inventory(db: AsyncSession) -> None:
    totals: dict[tuple[str, Decimal], Decimal] = {}
    for row in JUNE_ROWS:
        weight = _weight_grams(row.weight_per_piece)
        status = _classify(row.status_text)
        if status["fabric_received"]:
            totals[("June PDF Fabric", Decimal(weight))] = totals.get(("June PDF Fabric", Decimal(weight)), Decimal("0")) + Decimal(row.qty)

    for (_fabric_type, gsm), meters in sorted(totals.items(), key=lambda item: item[0][1]):
        db.add(
            FabricInventory(
                fabric_type="June PDF Fabric",
                color="Assorted",
                gsm=gsm,
                width=Decimal("100"),
                available_length_m=meters,
                approximate_rolls=None,
            )
        )
    await db.flush()


async def _seed_pos(db: AsyncSession, owner_id: Any) -> dict[str, int]:
    stats = {
        "pos_created": 0,
        "products_created": 0,
        "fabric_ready": 0,
        "shortage": 0,
        "mill_orders": 0,
        "dispatch_loads": 0,
    }
    for index, row in enumerate(JUNE_ROWS, start=1):
        po_number = f"JUNE-{index:03d}"
        status_info = _classify(row.status_text)
        if status_info["po_status"] == POStatus.dispatch and status_info["ready_pieces"] == 0 and status_info["shipped_pieces"] == 0:
            status_info["ready_pieces"] = row.qty
        per_piece_m = _fabric_meter_factor(row)
        pieces_in_stock = min(status_info["ready_pieces"], row.qty)
        pieces_short = max(row.qty - pieces_in_stock, 0) if status_info["shortage"] else 0
        stock_meters = Decimal(row.qty if status_info["fabric_received"] else 0)
        product = Product(
            product_name=row.category,
            product_category="category",
            size=_size_from_category(row.category),
            design=_design_from_category(row.category),
            color=_color_from_category(row.category),
            fabric_type="June PDF Fabric",
            gsm=Decimal(_weight_grams(row.weight_per_piece)),
            width=Decimal("100"),
            per_piece_fabric_usage_m=per_piece_m,
            wastage_percent=Decimal("0"),
            roll_length_m=None,
            product_photo_url=None,
        )
        db.add(product)
        await db.flush()
        stats["products_created"] += 1

        po = PurchaseOrder(
            po_number=po_number,
            product_id=product.id,
            order_quantity_pcs=row.qty,
            mrp=None,
            selling_price=None,
            order_date=SEED_ORDER_DATE,
            promise_delivery_date=SEED_DEADLINE,
            status=status_info["po_status"],
            notes=(
                f"{SEED_MARKER}; PDF PO-Category={row.category}; PDF Status={row.status_text or 'Not provided'}; "
                f"Weight/Pcs={row.weight_per_piece}; Volume Metric={row.volume_metric or 'Not provided'}"
            ),
            fabric_design_id=None,
            design_name_snapshot=row.category,
            design_code_snapshot=po_number,
            design_image_url_snapshot=None,
            design_status=PODesignStatus.custom_design,
            priority_level=_priority_for_status(row.status_text),
            priority_reason="Imported from June POs Status.pdf",
            created_by=owner_id,
        )
        db.add(po)
        await db.flush()
        stats["pos_created"] += 1

        line = ProductFabricLine(
            product_id=product.id,
            fabric_code=row.category,
            pieces=row.qty,
            pieces_in_stock=pieces_in_stock,
            pieces_short=pieces_short,
            stock_status="short" if status_info["shortage"] else "in_stock" if pieces_in_stock else "ok",
            per_piece_meters=per_piece_m,
            stock_meters=stock_meters,
            pieces_per_bale=PIECES_PER_BALE,
            bale_size_cbm=_bale_cbm(row),
            bale_weight_kg=_bale_weight(row),
            cutting=status_info["line_cutting"],
            stitching=status_info["line_stitching"],
            packing=status_info["line_packing"],
            dispatch=status_info["line_dispatch"],
            notes=f"{SEED_MARKER}; PDF status: {row.status_text or 'blank'}",
        )
        db.add(line)
        await db.flush()

        required_m = (Decimal(max(row.qty - pieces_in_stock, 0)) * per_piece_m).quantize(Decimal("0.001"))
        available_m = stock_meters.quantize(Decimal("0.001"))
        shortage_m = max(required_m - available_m, Decimal("0.000")).quantize(Decimal("0.001"))
        if status_info["fabric_received"] and not status_info["shortage"]:
            available_m = required_m
            shortage_m = Decimal("0.000")
        plan_status = FabricPlanStatus.shortage if shortage_m > 0 else FabricPlanStatus.fabric_ready
        db.add(
            FabricPlan(
                purchase_order_id=po.id,
                required_m=required_m,
                wastage_m=Decimal("0.000"),
                total_required_m=required_m,
                roll_length_m=None,
                rolls_required=None,
                available_m=available_m,
                shortage_m=shortage_m,
                status=plan_status,
            )
        )
        if shortage_m > 0:
            stats["shortage"] += 1
            await _seed_shortage_records(db, po, product, shortage_m, row, status_info)
            stats["mill_orders"] += 1
        else:
            stats["fabric_ready"] += 1
        await _seed_stage_rows(db, po, status_info)
        if status_info["shipped_pieces"] > 0:
            await _seed_dispatch_load(db, po, row, status_info["shipped_pieces"])
            stats["dispatch_loads"] += 1
        if status_info["fabric_received"]:
            db.add(
                FabricReceipt(
                    purchase_order_id=po.id,
                    supplier_name="June PDF received stock",
                    fabric_type=product.fabric_type,
                    color=product.color,
                    gsm=product.gsm,
                    width=product.width,
                    received_length_m=max(required_m, available_m),
                    approximate_rolls=None,
                    status=ReceiptStatus.approved,
                    quality_notes=f"{SEED_MARKER}: fabric received according to June status sheet.",
                    received_at=SEED_ORDER_DATE,
                )
            )
    return stats


async def _seed_shortage_records(
    db: AsyncSession,
    po: PurchaseOrder,
    product: Product,
    shortage_m: Decimal,
    row: JuneRow,
    status_info: dict[str, Any],
) -> None:
    db.add(
        MillOrderRequirement(
            purchase_order_id=po.id,
            required_meters=float(row.qty),
            available_meters=float(row.qty) - float(shortage_m),
            shortage_meters=float(shortage_m),
            gsm=float(product.gsm),
            fabric_type=product.fabric_type,
            design=row.category,
            color=product.color,
            suggested_order_meters=float(shortage_m),
            status=MillOrderRequirementStatus.mill_order_created,
        )
    )
    delivery_date = SEED_ORDER_DATE + timedelta(days=7)
    mill_name = _mill_for_row(row)
    db.add(
        FabricMillOrder(
            purchase_order_id=po.id,
            mill_name=mill_name,
            invoice_number=f"{po.po_number}-FAB-01",
            ordered_meters=shortage_m,
            ordered_width=product.width,
            ordered_gsm=product.gsm,
            ordered_rate_per_meter=None,
            expected_quality_notes="June PDF shortage/order record",
            committed_delivery_date=delivery_date,
            actual_delivery_date=None,
            status=FabricMillOrderStatus.ordered,
            remarks=f"{SEED_MARKER}: {row.status_text}",
        )
    )
    db.add(
        Alert(
            purchase_order_id=po.id,
            alert_type=AlertType.stock_shortage,
            priority=AlertPriority.critical if "not in stock" in row.status_text.lower() else AlertPriority.high,
            title="Fabric order pending",
            message=f"{row.category}: fabric/order still pending from June status sheet.",
            is_resolved=False,
        )
    )
    db.add(
        Reminder(
            purchase_order_id=po.id,
            reminder_type=ReminderType.fabric_order_pending,
            title="Follow up fabric order",
            message=f"Follow up {mill_name} for {row.category}.",
            due_date=SEED_ORDER_DATE,
            assigned_to=None,
            priority=ReminderPriority.high,
            status=ReminderStatus.open,
        )
    )


async def _seed_stage_rows(db: AsyncSession, po: PurchaseOrder, status_info: dict[str, Any]) -> None:
    qty = int(po.order_quantity_pcs)
    shipped = int(status_info["shipped_pieces"])
    ready = int(status_info["ready_pieces"])
    active_stage: StageName | None = status_info["active_stage"]
    for sequence, stage in enumerate(
        (
            StageName.fabric_ready,
            StageName.cutting,
            StageName.stitching,
            StageName.size_inspection,
            StageName.quality_check,
            StageName.packing,
            StageName.dispatch,
        )
    ):
        attrs = _stage_attrs(stage, active_stage, qty, ready, shipped, status_info)
        db.add(StageSummary(purchase_order_id=po.id, stage=stage, sequence=sequence, **attrs))
    await db.flush()


def _stage_attrs(stage: StageName, active_stage: StageName | None, qty: int, ready: int, shipped: int, info: dict[str, Any]) -> dict[str, Any]:
    if info["shortage"] and active_stage == StageName.fabric_ready:
        if stage == StageName.fabric_ready:
            done = ready
            return _stage_dict(qty, done, StageStatus.blocked)
        if ready > 0 and stage in {StageName.packing, StageName.dispatch}:
            if stage == StageName.packing:
                return _stage_dict(ready, ready, StageStatus.completed)
            return _stage_dict(ready, shipped, StageStatus.in_progress if ready - shipped > 0 else StageStatus.completed)
        return _stage_dict(0, 0, StageStatus.not_started)

    ordered_stages = [
        StageName.fabric_ready,
        StageName.cutting,
        StageName.stitching,
        StageName.size_inspection,
        StageName.quality_check,
        StageName.packing,
        StageName.dispatch,
    ]
    if active_stage is None:
        return _stage_dict(0, 0, StageStatus.not_started)
    active_index = ordered_stages.index(active_stage)
    stage_index = ordered_stages.index(stage)
    if stage == StageName.dispatch:
        dispatch_input = ready if ready > 0 else qty if active_stage == StageName.dispatch else 0
        return _stage_dict(dispatch_input, shipped, StageStatus.in_progress if dispatch_input > shipped else StageStatus.completed if shipped else StageStatus.not_started)
    if stage_index < active_index:
        return _stage_dict(qty, qty, StageStatus.completed)
    if stage_index == active_index:
        completed = ready if stage == StageName.packing else 0
        return _stage_dict(qty, completed, StageStatus.in_progress)
    return _stage_dict(0, 0, StageStatus.not_started)


def _stage_dict(input_qty: int, completed_qty: int, status: StageStatus) -> dict[str, Any]:
    completed_qty = min(int(completed_qty), int(input_qty))
    return {
        "input_qty": int(input_qty),
        "completed_qty": completed_qty,
        "approved_qty": completed_qty,
        "rejected_qty": 0,
        "repair_qty": 0,
        "alter_qty": 0,
        "moved_to_next_qty": completed_qty,
        "pending_qty": max(int(input_qty) - completed_qty, 0),
        "status": status,
    }


async def _seed_dispatch_load(db: AsyncSession, po: PurchaseOrder, row: JuneRow, shipped_pieces: int) -> None:
    shipped_pieces = min(shipped_pieces, row.qty)
    db.add(
        DispatchLoad(
            purchase_order_id=po.id,
            load_number=f"{po.po_number}-LOAD-01",
            shipped_qty=shipped_pieces,
            vehicle_type="14 feet",
            vehicle_identifier=None,
            expected_piece_capacity=None,
            actual_loaded_pieces=shipped_pieces,
            cbm_capacity=Decimal("14"),
            cbm_used=(Decimal(shipped_pieces) * _piece_cbm(row)).quantize(Decimal("0.001")),
            cost_type=DispatchCostType.vehicle_capacity,
            invoice_value=None,
            dispatch_percent=None,
            cbm_value=None,
            cbm_rate=None,
            manual_cost=None,
            vehicle_cost=Decimal("0.00"),
            dispatch_cost=Decimal("0.00"),
            cost_per_piece=Decimal("0.0000"),
            shipped_at=SEED_ORDER_DATE,
            transporter_name="Haryana Transport",
            destination=None,
            tracking_reference=None,
            document_status="complete",
            invoice_uploaded=True,
            packing_list_uploaded=True,
            eway_bill_uploaded=True,
            transporter_confirmation=True,
            buyer_dispatch_approval=True,
            shortfall_qty=max(row.qty - shipped_pieces, 0),
            shortfall_reason="Balance pending per June status sheet" if shipped_pieces < row.qty else None,
            linked_repair_qty=0,
            linked_alteration_qty=0,
            remarks=f"{SEED_MARKER}: {row.status_text}",
        )
    )


def _classify(status_text: str) -> dict[str, Any]:
    text = status_text.lower().strip()
    ready_pieces = _extract_pieces(text, "ready") or _extract_pieces(text, "stock") or 0
    shipped_pieces = _extract_pieces(text, "dispatched") or 0
    fabric_received = "fabric recieved" in text or "fabric received" in text or "balance fabric received" in text
    shortage = (
        "orderd but not received" in text
        or "ordered but not received" in text
        or "not in stock" in text
        or "balance fabric order" in text
        or "balance fabric required" in text
        or text == ""
    )
    if "today dispatch" in text or text == "ready":
        active = StageName.dispatch
        po_status = POStatus.dispatch
        ready_pieces = ready_pieces or 10**9
    elif "dispatched" in text:
        active = StageName.dispatch
        po_status = POStatus.partially_dispatched
    elif "in stitching" in text:
        active = StageName.stitching
        po_status = POStatus.stitching
    elif "stitiched" in text or "stitched" in text:
        active = StageName.packing
        po_status = POStatus.packing
    elif shortage:
        active = StageName.fabric_ready
        po_status = POStatus.shortage
    else:
        active = StageName.cutting
        po_status = POStatus.fabric_ready

    if fabric_received and not shortage:
        active = active or StageName.cutting
    if ready_pieces == 10**9:
        ready_pieces = 0

    return {
        "fabric_received": fabric_received,
        "shortage": shortage,
        "ready_pieces": ready_pieces,
        "shipped_pieces": shipped_pieces,
        "active_stage": active,
        "po_status": po_status,
        "line_cutting": "done" if active not in {StageName.fabric_ready, StageName.cutting} else "pending" if active == StageName.fabric_ready else "in_progress",
        "line_stitching": "done" if active not in {StageName.fabric_ready, StageName.cutting, StageName.stitching} else "pending" if active in {StageName.fabric_ready, StageName.cutting} else "in_progress",
        "line_packing": "done" if active == StageName.dispatch else "pending" if active != StageName.packing else "in_progress",
        "line_dispatch": "done" if shipped_pieces > 0 else "pending" if active == StageName.dispatch else "pending",
    }


def _extract_pieces(text: str, word: str) -> int:
    # Handles "2000pcs in stock", "1200pcs Ready", "3000 Dispatched".
    patterns = [
        rf"(\d[\d,]*)\s*pcs?\s*(?:in\s*)?{word}",
        rf"(\d[\d,]*)\s*{word}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", ""))
    return 0


def _weight_grams(value: str) -> int:
    clean = value.strip().lower()
    if clean.endswith("kg"):
        return int(Decimal(clean.replace("kg", "").strip() or "1") * 1000)
    match = re.search(r"(\d+)", clean)
    return int(match.group(1)) if match else 0


def _piece_cbm(row: JuneRow) -> Decimal:
    value = (row.volume_metric or "").strip()
    if not value or value.upper() == "N/A":
        return _fallback_piece_cbm(row.weight_per_piece)
    return Decimal(value)


def _fallback_piece_cbm(weight: str) -> Decimal:
    grams = _weight_grams(weight)
    if grams <= 80:
        return Decimal("0.0005")
    if grams <= 320:
        return Decimal("0.001493")
    if grams <= 450:
        return Decimal("0.0019")
    if grams <= 750:
        return Decimal("0.0027")
    return Decimal("0.0035")


def _fabric_meter_factor(row: JuneRow) -> Decimal:
    # Updated from owner-provided WhatsApp photo dated 2026-06-04. The third
    # column in that photo is the meter-per-piece fabric consumption.
    category = row.category.upper()
    if category.startswith("109-"):
        return Decimal("1.420")
    if "MISTY" in category or "TEAL" in category:
        return Decimal("1.750")
    if "CHARCOAL" in category:
        return Decimal("1.430")
    if "SAGE-GRID" in category or "EARTHY-ABSTRACT" in category or "MODERN-GEO" in category:
        return Decimal("2.850")
    if "JAIPURI" in category:
        return Decimal("2.950")
    if "GOLD-STEM" in category or "GOLD-STEAM" in category or "MODERN-STONE" in category:
        return Decimal("2.850")
    if "FITTED" in category:
        return Decimal("3.100")
    if "PREMIUM" in category or "WHITEBEAUTY" in category or "WHITE-BEAUTY" in category:
        return Decimal("3.350")
    return Decimal("1.000")


def _bale_cbm(row: JuneRow) -> Decimal:
    return (_piece_cbm(row) * Decimal(PIECES_PER_BALE)).quantize(Decimal("0.0001"))


def _bale_weight(row: JuneRow) -> Decimal:
    return (Decimal(_weight_grams(row.weight_per_piece)) / Decimal("1000") * Decimal(PIECES_PER_BALE)).quantize(Decimal("0.01"))


def _size_from_category(category: str) -> str:
    match = re.search(r"(\d{2,3}X\d{2,3})", category, re.IGNORECASE)
    return match.group(1).replace("X", " x ") if match else "As per PO"


def _design_from_category(category: str) -> str:
    parts = category.split("-")
    if len(parts) < 3:
        return category[:120]
    size_index = next((i for i, part in enumerate(parts) if re.match(r"^\d{2,3}X\d{2,3}$", part, re.I)), len(parts))
    return "-".join(parts[1:size_index])[:120] or category[:120]


def _color_from_category(category: str) -> str:
    parts = category.split("-")
    return (parts[1] if len(parts) > 1 else "Assorted")[:80]


def _priority_for_status(status_text: str) -> str:
    text = status_text.lower()
    if "not in stock" in text or "balance fabric required" in text:
        return "urgent"
    if "orderd but not received" in text or "ordered but not received" in text or "in stitching" in text:
        return "high"
    return "normal"


def _mill_for_row(row: JuneRow) -> str:
    if row.category.startswith("99") or row.category.startswith("199"):
        return "Shivam Mill"
    if row.category.startswith("299"):
        return "Krishna Mill"
    if row.category.startswith("499"):
        return "XYZ Mill"
    return "Krishna Mill"


if __name__ == "__main__":
    asyncio.run(main())
