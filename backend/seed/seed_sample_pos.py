from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models.alert import Alert
from app.models.capacity import CapacityProfile
from app.models.contractor import Contractor
from app.models.dispatch import DispatchLoad
from app.models.enums import (
    AlertPriority,
    AlertType,
    CapacityStage,
    ContractorType,
    DispatchCostType,
    FabricMillOrderStatus,
    FabricPlanStatus,
    FabricVerificationAction,
    FabricVerificationStatus,
    POStatus,
    ProductType,
    QualityAction,
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
    MillFollowUp,
    SupplierReturn,
)
from app.models.mill_requirement import MillOrderRequirement, MillOrderRequirementStatus
from app.models.po_draft import PODraft, PODraftStatus
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import Reminder, ReminderPriority, ReminderStatus, ReminderType
from app.models.stage import (
    ContractorAllocation,
    CuttingAnalysis,
    PackingOutput,
    QCInspection,
    QualityFailure,
    StageCostEntry,
    StageProgressEntry,
    StageSummary,
)
from app.models.user import User
from app.schemas.capacity import CapacityProfileCreate
from app.schemas.dispatch import DispatchLoadCreate
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.stage import (
    CuttingAnalysisCreate,
    ContractorAllocationCreate,
    PackingOutputCreate,
    QCInspectionCreate,
    QualityFailureCreate,
    StageCostEntryCreate,
    StageProgressCreate,
)
from app.services.alert_engine import generate_alerts
from app.services.capacity_planning import create_capacity_profile, detect_underutilization
from app.services.dispatch_engine import create_dispatch_load
from app.services.fabric_operations import upsert_cutting_analysis
from app.services.fabric_planning import calculate_fabric_plan
from app.services.purchase_order_service import create_purchase_order
from app.services.stage_engine import (
    allocate_contractor,
    create_qc_inspection,
    create_stage_cost_entry,
    record_quality_failure,
    record_stage_progress,
    update_packing_output,
)


SEED_MARKER = "SEED_SAMPLE_PO_2026"
SEED_PRODUCT_CATEGORY = "seed_sample_po"
SEED_NOTES = f"{SEED_MARKER} realistic workflow demo"
TODAY = date(2026, 5, 7)


@dataclass(frozen=True)
class POSeed:
    po_number: str
    product_name: str
    product_type: ProductType
    design: str
    color: str
    size: str
    gsm: Decimal
    width: Decimal
    meter_per_piece: Decimal
    wastage_percent: Decimal
    quantity: int
    order_date: date
    shipment_date: date
    mrp: Decimal
    selling_price: Decimal
    fabric_type: str


def d(value: Any) -> Decimal:
    return Decimal(str(value))


PO_SEEDS: list[POSeed] = [
    POSeed("DBL-2026-001", "Flowers Double Bed Sheet", ProductType.double_bedsheet, "Floral", "Blue", "78 x 98 inch", d(150), d(78), d(3), d(0.1), 12000, date(2026, 5, 6), date(2026, 5, 30), d(300), d(180), "Cotton Percale [SEED]"),
    POSeed("DBL-2026-002", "Stripe Double Bed Sheet", ProductType.double_bedsheet, "Stripe", "Grey", "78 x 98 inch", d(145), d(78), d(2.9), d(0.5), 8000, date(2026, 5, 7), date(2026, 5, 28), d(320), d(195), "Cotton Percale [SEED]"),
    POSeed("DBL-2026-003", "Premium Double Bed Sheet", ProductType.double_bedsheet, "Premium Weave", "Ivory", "80 x 100 inch", d(160), d(80), d(3.2), d(0.7), 15000, date(2026, 5, 8), date(2026, 6, 5), d(350), d(210), "Cotton Sateen [SEED]"),
    POSeed("SGL-2026-001", "Plain Single Bed Sheet", ProductType.single_bedsheet, "Plain", "White", "60 x 90 inch", d(130), d(60), d(2.1), d(0.3), 10000, date(2026, 5, 6), date(2026, 5, 25), d(220), d(135), "Cotton Blend [SEED]"),
    POSeed("SGL-2026-002", "Kids Print Single Bed Sheet", ProductType.single_bedsheet, "Kids Print", "Yellow", "60 x 90 inch", d(135), d(60), d(2.2), d(0.4), 6000, date(2026, 5, 9), date(2026, 5, 27), d(240), d(150), "Cotton Blend [SEED]"),
    POSeed("SGL-2026-003", "Economy Single Bed Sheet", ProductType.single_bedsheet, "Economy Plain", "Cream", "58 x 88 inch", d(125), d(58), d(2.0), d(0.6), 18000, date(2026, 5, 10), date(2026, 6, 8), d(200), d(120), "Poly Cotton [SEED]"),
    POSeed("FIT-2026-001", "Elastic Fitted Bed Sheet", ProductType.fitted_sheet, "Elastic Fit", "Teal", "78 x 98 x 10 inch", d(155), d(78), d(3.4), d(0.8), 5000, date(2026, 5, 6), date(2026, 5, 24), d(420), d(260), "Cotton Lycra [SEED]"),
    POSeed("FIT-2026-002", "Printed Fitted Bed Sheet", ProductType.fitted_sheet, "Printed", "Rose", "78 x 98 x 12 inch", d(160), d(78), d(3.6), d(1.0), 7000, date(2026, 5, 8), date(2026, 6, 1), d(450), d(280), "Cotton Lycra [SEED]"),
    POSeed("FIT-2026-003", "Premium Fitted Bed Sheet", ProductType.fitted_sheet, "Premium Fitted", "Charcoal", "80 x 100 x 12 inch", d(170), d(80), d(3.8), d(1.2), 4000, date(2026, 5, 11), date(2026, 6, 3), d(500), d(310), "Sateen Stretch [SEED]"),
    POSeed("KNG-2026-001", "Luxury King Bed Sheet", ProductType.king_bedsheet, "Luxury", "Navy", "90 x 108 inch", d(165), d(90), d(3.8), d(0.8), 9000, date(2026, 5, 6), date(2026, 5, 31), d(480), d(300), "King Cotton [SEED]"),
    POSeed("KNG-2026-002", "Floral King Bed Sheet", ProductType.king_bedsheet, "Floral", "Lavender", "90 x 108 inch", d(170), d(90), d(4.0), d(1.0), 11000, date(2026, 5, 9), date(2026, 6, 6), d(520), d(330), "King Cotton [SEED]"),
    POSeed("KNG-2026-003", "Hotel King Bed Sheet", ProductType.king_bedsheet, "Hotel Stripe", "White", "92 x 110 inch", d(180), d(92), d(4.2), d(1.1), 7500, date(2026, 5, 12), date(2026, 6, 10), d(550), d(350), "Hotel Linen [SEED]"),
    POSeed("PIL-2026-001", "Standard Pillow Cover", ProductType.pillow, "Plain", "White", "18 x 28 inch", d(120), d(18), d(0.65), d(0.5), 20000, date(2026, 5, 6), date(2026, 5, 26), d(80), d(45), "Pillow Cotton [SEED]"),
    POSeed("PIL-2026-002", "Printed Pillow Cover", ProductType.pillow, "Printed", "Mint", "18 x 28 inch", d(125), d(18), d(0.7), d(0.7), 16000, date(2026, 5, 7), date(2026, 5, 29), d(90), d(55), "Pillow Cotton [SEED]"),
    POSeed("PIL-2026-003", "Premium Pillow Cover", ProductType.pillow, "Premium Printed", "Maroon", "20 x 30 inch", d(135), d(20), d(0.8), d(0.9), 12000, date(2026, 5, 10), date(2026, 6, 2), d(110), d(70), "Pillow Satin [SEED]"),
]

CONTRACTOR_SEEDS: list[tuple[str, ContractorType]] = [
    ("Cutting Contractor A", ContractorType.cutting),
    ("Cutting Contractor B", ContractorType.cutting),
    ("Stitching Contractor A", ContractorType.stitching),
    ("Stitching Contractor B", ContractorType.stitching),
    ("Stitching Contractor C", ContractorType.stitching),
    ("Packing Team A", ContractorType.packing),
    ("Packing Team B", ContractorType.packing),
    ("Haryana Transport", ContractorType.transport),
    ("Delhi Cargo Movers", ContractorType.transport),
]

INVENTORY_COVERAGE: dict[str, Decimal] = {
    "DBL-2026-001": d("1.05"),
    "DBL-2026-002": d("1.02"),
    "DBL-2026-003": d("0.52"),
    "SGL-2026-001": d("1.08"),
    "SGL-2026-002": d("0.35"),
    "SGL-2026-003": d("0.00"),
    "FIT-2026-001": d("1.03"),
    "FIT-2026-002": d("0.25"),
    "FIT-2026-003": d("0.00"),
    "KNG-2026-001": d("1.04"),
    "KNG-2026-002": d("0.40"),
    "KNG-2026-003": d("0.22"),
    "PIL-2026-001": d("1.10"),
    "PIL-2026-002": d("1.06"),
    "PIL-2026-003": d("0.30"),
}


async def ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_schema_compat(conn)


async def _apply_schema_compat(conn: Any) -> None:
    statements = [
        # Enum upgrades for legacy docker schema.
        "ALTER TYPE dispatch_cost_type ADD VALUE IF NOT EXISTS 'vehicle_capacity';",
        "ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'high_cutting_wastage';",
        "ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'capacity_risk';",
        "ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'cutting_underutilization';",
        "ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'stitching_underutilization';",
        "ALTER TYPE alert_type ADD VALUE IF NOT EXISTS 'packing_underutilization';",
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fabric_verification_status') THEN
            CREATE TYPE fabric_verification_status AS ENUM ('pending', 'approved', 'mismatch', 'rejected', 'returned');
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fabric_verification_action') THEN
            CREATE TYPE fabric_verification_action AS ENUM ('accept', 'return_to_supplier', 'reopen_shortage', 'adjust_consumption', 'hold');
          END IF;
        END $$;
        """,
        # products
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS product_photo_url varchar(500);",
        # contractor allocations
        "ALTER TABLE contractor_allocations ADD COLUMN IF NOT EXISTS assigned_to uuid;",
        "ALTER TABLE contractor_allocations ADD COLUMN IF NOT EXISTS responsible_role varchar(80);",
        "ALTER TABLE contractor_allocations ADD COLUMN IF NOT EXISTS completed_by uuid;",
        "ALTER TABLE contractor_allocations ADD COLUMN IF NOT EXISTS completed_at timestamptz;",
        "ALTER TABLE contractor_allocations ADD COLUMN IF NOT EXISTS remarks text;",
        # stage progress
        "ALTER TABLE stage_progress_entries ADD COLUMN IF NOT EXISTS assigned_to uuid;",
        "ALTER TABLE stage_progress_entries ADD COLUMN IF NOT EXISTS responsible_role varchar(80);",
        "ALTER TABLE stage_progress_entries ADD COLUMN IF NOT EXISTS completed_by uuid;",
        "ALTER TABLE stage_progress_entries ADD COLUMN IF NOT EXISTS completed_at timestamptz;",
        # quality failures
        "ALTER TABLE quality_failures ADD COLUMN IF NOT EXISTS resolved_qty integer NOT NULL DEFAULT 0;",
        "ALTER TABLE quality_failures ADD COLUMN IF NOT EXISTS pending_resolution_qty integer NOT NULL DEFAULT 0;",
        "ALTER TABLE quality_failures ADD COLUMN IF NOT EXISTS assigned_to uuid;",
        "ALTER TABLE quality_failures ADD COLUMN IF NOT EXISTS responsible_role varchar(80);",
        "ALTER TABLE quality_failures ADD COLUMN IF NOT EXISTS completed_by uuid;",
        "ALTER TABLE quality_failures ADD COLUMN IF NOT EXISTS completed_at timestamptz;",
        "ALTER TABLE quality_failures ADD COLUMN IF NOT EXISTS remarks text;",
        # fabric receipts
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS received_width numeric(10, 2);",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS received_gsm numeric(10, 2);",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS received_rate_per_meter numeric(14, 2);",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS received_meters numeric(14, 3);",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS verified_by uuid;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS verification_date date;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS verification_status fabric_verification_status;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS mismatch_reason text;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS action_taken fabric_verification_action;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS assigned_to uuid;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS responsible_role varchar(80);",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS completed_by uuid;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS completed_at timestamptz;",
        "ALTER TABLE fabric_receipts ADD COLUMN IF NOT EXISTS remarks text;",
        "UPDATE fabric_receipts SET verification_status='pending' WHERE verification_status IS NULL;",
        # dispatch loads
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS vehicle_type varchar(100);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS vehicle_identifier varchar(100);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS expected_piece_capacity integer;",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS actual_loaded_pieces integer;",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS cbm_capacity numeric(14, 3);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS cbm_used numeric(14, 3);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS vehicle_cost numeric(14, 2);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS expected_cost_percent numeric(8, 3);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS actual_cost_percent numeric(8, 3);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS assigned_to uuid;",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS responsible_role varchar(80);",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS completed_by uuid;",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS completed_at timestamptz;",
        "ALTER TABLE dispatch_loads ADD COLUMN IF NOT EXISTS remarks varchar(500);",
    ]
    for stmt in statements:
        await conn.execute(text(stmt))


async def ensure_seed_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    existing = result.scalars().first()
    if existing is not None:
        return existing
    user = User(
        full_name="Seed Manager",
        email="seed.manager@example.com",
        password_hash=hash_password("SeedManager@2026"),
        role=UserRole.manager,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def reset_seed_data(db: AsyncSession) -> None:
    # Full operational reset: clear all workflow/demo data while preserving users.
    # Order is important to satisfy foreign-key dependencies.
    await db.execute(delete(Alert))
    await db.execute(delete(Reminder))
    await db.execute(delete(DispatchLoad))
    await db.execute(delete(PackingOutput))
    await db.execute(delete(QCInspection))
    await db.execute(delete(QualityFailure))
    await db.execute(delete(StageProgressEntry))
    await db.execute(delete(ContractorAllocation))
    await db.execute(delete(StageSummary))
    await db.execute(delete(StageCostEntry))
    await db.execute(delete(CuttingAnalysis))

    await db.execute(delete(FabricIssueToCutting))
    await db.execute(delete(MillFollowUp))
    await db.execute(delete(FabricMillOrder))
    await db.execute(delete(SupplierReturn))
    await db.execute(delete(DebitNote))
    await db.execute(delete(FabricReceipt))
    await db.execute(delete(MillOrderRequirement))
    await db.execute(delete(FabricPlan))

    await db.execute(delete(PODraft))
    await db.execute(delete(PurchaseOrder))
    await db.execute(delete(FabricInventory))
    await db.execute(delete(CapacityProfile))
    await db.execute(delete(Contractor))
    await db.execute(delete(Product))
    await db.commit()


def _fabric_totals(seed: POSeed) -> tuple[Decimal, Decimal, Decimal]:
    values = calculate_fabric_plan(seed.quantity, seed.meter_per_piece, seed.wastage_percent, None)
    return values["required_m"], values["wastage_m"], values["total_required_m"]


async def create_seed_products(db: AsyncSession) -> dict[str, Product]:
    products: dict[str, Product] = {}
    for row in PO_SEEDS:
        product = Product(
            product_name=row.product_name,
            product_category=SEED_PRODUCT_CATEGORY,
            size=row.size,
            design=row.design,
            color=row.color,
            fabric_type=row.fabric_type,
            gsm=row.gsm,
            width=row.width,
            per_piece_fabric_usage_m=row.meter_per_piece,
            wastage_percent=row.wastage_percent,
            roll_length_m=d("95"),
            product_photo_url=f"https://example.com/seed/{row.po_number.lower()}.jpg",
        )
        db.add(product)
        await db.flush()
        products[row.po_number] = product
    await db.commit()
    for product in products.values():
        await db.refresh(product)
    return products


async def create_seed_inventory(db: AsyncSession, products: dict[str, Product]) -> dict[str, FabricInventory]:
    inventory_by_po: dict[str, FabricInventory] = {}
    for seed in PO_SEEDS:
        coverage = INVENTORY_COVERAGE[seed.po_number]
        _, _, total_required = _fabric_totals(seed)
        available = (total_required * coverage).quantize(Decimal("0.001"))
        if available <= 0:
            continue
        inventory = FabricInventory(
            fabric_type=seed.fabric_type,
            color=seed.color,
            gsm=seed.gsm,
            width=seed.width,
            available_length_m=available,
            approximate_rolls=None,
        )
        db.add(inventory)
        await db.flush()
        inventory_by_po[seed.po_number] = inventory
    await db.commit()
    return inventory_by_po


async def create_seed_contractors(db: AsyncSession) -> dict[str, Contractor]:
    contractors: dict[str, Contractor] = {}
    for name, ctype in CONTRACTOR_SEEDS:
        contractor = Contractor(
            name=name,
            contractor_type=ctype,
            phone="+91-9876500000",
            email=f"{name.lower().replace(' ', '.')}@example.com",
            is_active=True,
        )
        db.add(contractor)
        await db.flush()
        contractors[name] = contractor
    await db.commit()
    return contractors


async def create_seed_pos(db: AsyncSession, user: User, products: dict[str, Product]) -> dict[str, PurchaseOrder]:
    pos: dict[str, PurchaseOrder] = {}
    for row in PO_SEEDS:
        payload = PurchaseOrderCreate(
            po_number=row.po_number,
            product_id=products[row.po_number].id,
            order_quantity_pcs=row.quantity,
            mrp=row.mrp,
            selling_price=row.selling_price,
            order_date=row.order_date,
            promise_delivery_date=row.shipment_date,
            notes=SEED_NOTES,
        )
        po = await create_purchase_order(db, payload, user.id)
        pos[row.po_number] = po
    return pos


async def create_po_drafts(db: AsyncSession, user: User) -> None:
    draft_1 = PODraft(
        raw_input_text=f"{SEED_MARKER}: PO quantity 12000, order date 6 May 2026, shipment date 30 May 2026, product Flowers Double Bed Sheet, 3 meter per piece",
        quantity_pieces=12000,
        order_date=date(2026, 5, 6),
        shipment_date=date(2026, 5, 30),
        product_name="Flowers Double Bed Sheet",
        meter_per_piece=d(3),
        confidence_score=0.91,
        status=PODraftStatus.confirmed,
        created_by=user.id,
        extracted_fields_json={"po_number": "DBL-2026-001"},
        missing_fields_json=[],
    )
    draft_2 = PODraft(
        raw_input_text=f"{SEED_MARKER}: PO quantity 7000, order date 8 May 2026, product Printed Fitted Bed Sheet",
        quantity_pieces=7000,
        order_date=date(2026, 5, 8),
        product_name="Printed Fitted Bed Sheet",
        confidence_score=0.57,
        status=PODraftStatus.needs_review,
        created_by=user.id,
        extracted_fields_json={"quantity_pieces": 7000},
        missing_fields_json=["shipment_date", "gsm", "meter_per_piece"],
    )
    db.add_all([draft_1, draft_2])
    await db.commit()


async def create_shortages_mill_requirements_and_reminders(
    db: AsyncSession, pos: dict[str, PurchaseOrder], user: User
) -> dict[str, MillOrderRequirement]:
    requirements: dict[str, MillOrderRequirement] = {}
    for po_number, po in pos.items():
        await db.refresh(po, attribute_names=["fabric_plan", "product"])
        plan = po.fabric_plan
        if plan is None or plan.status != FabricPlanStatus.shortage:
            continue
        requirement = MillOrderRequirement(
            purchase_order_id=po.id,
            required_meters=float(plan.total_required_m),
            available_meters=float(plan.available_m),
            shortage_meters=float(plan.shortage_m),
            gsm=float(po.product.gsm) if po.product else None,
            fabric_type=po.product.fabric_type if po.product else None,
            design=po.product.design if po.product else None,
            color=po.product.color if po.product else None,
            suggested_order_meters=float(plan.shortage_m),
            status=MillOrderRequirementStatus.pending_mill_selection,
        )
        reminder = Reminder(
            purchase_order_id=po.id,
            reminder_type=ReminderType.fabric_order_pending,
            title="Fabric order pending",
            message=f"Fabric shortage exists for PO {po.po_number}. Mill order needs to be created.",
            due_date=TODAY,
            assigned_to=user.id,
            priority=ReminderPriority.high,
            status=ReminderStatus.open,
        )
        db.add_all([requirement, reminder])
        await db.flush()
        requirements[po_number] = requirement
    await db.commit()
    return requirements


async def create_mill_orders_followups_and_receipts(
    db: AsyncSession, pos: dict[str, PurchaseOrder], requirements: dict[str, MillOrderRequirement], user: User
) -> None:
    # 1) on-time order
    req = requirements.get("DBL-2026-003")
    if req is not None:
        order = FabricMillOrder(
            purchase_order_id=pos["DBL-2026-003"].id,
            mill_name="Surya Mills",
            ordered_meters=d(req.shortage_meters),
            ordered_width=d(80),
            ordered_gsm=d(160),
            ordered_rate_per_meter=d(92),
            expected_quality_notes="Matching premium weave",
            committed_delivery_date=date(2026, 5, 20),
            actual_delivery_date=None,
            status=FabricMillOrderStatus.ordered,
            responsible_user_id=user.id,
            assigned_to=user.id,
            responsible_role="manager",
            remarks=SEED_NOTES,
        )
        db.add(order)
        await db.flush()
        db.add(
            MillFollowUp(
                mill_order_id=order.id,
                followup_date=TODAY,
                followup_by=user.id,
                response_notes="Loom schedule confirmed.",
                next_followup_date=date(2026, 5, 10),
                status=FabricMillOrderStatus.in_followup,
                assigned_to=user.id,
                responsible_role="manager",
                remarks=SEED_NOTES,
            )
        )

    # 2) overdue order
    req = requirements.get("FIT-2026-002")
    if req is not None:
        order = FabricMillOrder(
            purchase_order_id=pos["FIT-2026-002"].id,
            mill_name="Anand Textile Mills",
            ordered_meters=d(req.shortage_meters),
            ordered_width=d(78),
            ordered_gsm=d(160),
            ordered_rate_per_meter=d(108),
            expected_quality_notes="Fitted elastic-compatible fabric",
            committed_delivery_date=date(2026, 5, 5),
            actual_delivery_date=None,
            status=FabricMillOrderStatus.delayed,
            responsible_user_id=user.id,
            assigned_to=user.id,
            responsible_role="manager",
            remarks=SEED_NOTES,
        )
        db.add(order)
        await db.flush()
        db.add(
            MillFollowUp(
                mill_order_id=order.id,
                followup_date=TODAY,
                followup_by=user.id,
                response_notes="Mill requested two more days.",
                next_followup_date=TODAY,
                status=FabricMillOrderStatus.delayed,
                assigned_to=user.id,
                responsible_role="manager",
                remarks=SEED_NOTES,
            )
        )

    # 3) partially received order
    req = requirements.get("KNG-2026-002")
    if req is not None:
        order = FabricMillOrder(
            purchase_order_id=pos["KNG-2026-002"].id,
            mill_name="Royal Looms",
            ordered_meters=d(req.shortage_meters),
            ordered_width=d(90),
            ordered_gsm=d(170),
            ordered_rate_per_meter=d(126),
            expected_quality_notes="Floral pattern color lock",
            committed_delivery_date=date(2026, 5, 18),
            actual_delivery_date=date(2026, 5, 6),
            status=FabricMillOrderStatus.partially_received,
            responsible_user_id=user.id,
            assigned_to=user.id,
            responsible_role="manager",
            remarks=SEED_NOTES,
        )
        db.add(order)
        await db.flush()
        db.add(
            MillFollowUp(
                mill_order_id=order.id,
                followup_date=TODAY,
                followup_by=user.id,
                response_notes="First lot received, balance in transit.",
                next_followup_date=date(2026, 5, 9),
                status=FabricMillOrderStatus.partially_received,
                assigned_to=user.id,
                responsible_role="manager",
                remarks=SEED_NOTES,
            )
        )

    # Verification pending receipt
    pending_receipt = FabricReceipt(
        purchase_order_id=pos["KNG-2026-002"].id,
        supplier_name="Royal Looms",
        fabric_type="King Cotton [SEED]",
        color="Lavender",
        gsm=d(170),
        width=d(90),
        received_length_m=d("8000.000"),
        approximate_rolls=80,
        status=ReceiptStatus.pending,
        quality_notes="Awaiting lab test",
        received_width=d(89.5),
        received_gsm=d(168),
        received_rate_per_meter=d(126),
        received_meters=d("8000.000"),
        verified_by=None,
        verification_date=None,
        verification_status=FabricVerificationStatus.pending,
        mismatch_reason=None,
        action_taken=None,
        assigned_to=user.id,
        responsible_role="qc",
        remarks=SEED_NOTES,
        received_at=TODAY,
    )
    db.add(pending_receipt)

    # Failed/rejected receipt with supplier return + debit note
    failed_receipt = FabricReceipt(
        purchase_order_id=pos["FIT-2026-002"].id,
        supplier_name="Anand Textile Mills",
        fabric_type="Cotton Lycra [SEED]",
        color="Rose",
        gsm=d(160),
        width=d(78),
        received_length_m=d("2200.000"),
        approximate_rolls=24,
        status=ReceiptStatus.failed,
        quality_notes="GSM mismatch and shade issue",
        received_width=d(77),
        received_gsm=d(150),
        received_rate_per_meter=d(108),
        received_meters=d("2200.000"),
        verified_by=user.id,
        verification_date=TODAY,
        verification_status=FabricVerificationStatus.rejected,
        mismatch_reason="GSM lower than ordered",
        action_taken=FabricVerificationAction.return_to_supplier,
        assigned_to=user.id,
        responsible_role="qc",
        completed_by=user.id,
        completed_at=datetime.now(timezone.utc),
        remarks=SEED_NOTES,
        received_at=TODAY,
    )
    db.add(failed_receipt)
    await db.flush()
    db.add(
        SupplierReturn(
            fabric_receipt_id=failed_receipt.id,
            supplier_name=failed_receipt.supplier_name,
            returned_length_m=failed_receipt.received_length_m,
            reason="Fabric verification failed",
            returned_at=TODAY,
        )
    )
    db.add(
        DebitNote(
            fabric_receipt_id=failed_receipt.id,
            supplier_name=failed_receipt.supplier_name,
            amount=d("18400.00"),
            reason="Rejected fabric return",
            note_date=TODAY,
        )
    )
    await db.commit()


async def _stage_map(db: AsyncSession, po_id: UUID) -> dict[StageName, StageSummary]:
    result = await db.execute(select(StageSummary).where(StageSummary.purchase_order_id == po_id))
    return {row.stage: row for row in result.scalars().all()}


async def create_allocations_progress_qc_dispatch(
    db: AsyncSession, pos: dict[str, PurchaseOrder], contractors: dict[str, Contractor], user: User
) -> int:
    dispatch_count = 0
    stage_maps: dict[str, dict[StageName, StageSummary]] = {}

    # DBL-2026-001 allocations
    sm = await _stage_map(db, pos["DBL-2026-001"].id)
    stage_maps["DBL-2026-001"] = sm
    dbl_cut_a = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.cutting].id,
            contractor_id=contractors["Cutting Contractor A"].id,
            issued_qty=5000,
            expected_completion_date=date(2026, 5, 16),
            notes=SEED_NOTES,
        ),
    )
    dbl_cut_b = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.cutting].id,
            contractor_id=contractors["Cutting Contractor B"].id,
            issued_qty=7000,
            expected_completion_date=date(2026, 5, 17),
            notes=SEED_NOTES,
        ),
    )
    await record_stage_progress(
        db,
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.cutting,
            allocation_id=dbl_cut_a.id,
            entry_date=date(2026, 5, 7),
            completed_today=5000,
            approved_today=5000,
            rejected_today=0,
            repair_today=0,
            alter_today=0,
            moved_to_next_stage_today=5000,
            remarks=SEED_NOTES,
        ),
    )
    await record_stage_progress(
        db,
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.cutting,
            allocation_id=dbl_cut_b.id,
            entry_date=date(2026, 5, 8),
            completed_today=7000,
            approved_today=7000,
            rejected_today=0,
            repair_today=0,
            alter_today=0,
            moved_to_next_stage_today=7000,
            remarks=SEED_NOTES,
        ),
    )
    sm = await _stage_map(db, pos["DBL-2026-001"].id)
    stage_maps["DBL-2026-001"] = sm
    dbl_stc_a = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.stitching].id,
            contractor_id=contractors["Stitching Contractor A"].id,
            issued_qty=4000,
            expected_completion_date=date(2026, 5, 20),
            notes=SEED_NOTES,
        ),
    )
    dbl_stc_b = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.stitching].id,
            contractor_id=contractors["Stitching Contractor B"].id,
            issued_qty=4000,
            expected_completion_date=date(2026, 5, 21),
            notes=SEED_NOTES,
        ),
    )
    dbl_stc_c = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.stitching].id,
            contractor_id=contractors["Stitching Contractor C"].id,
            issued_qty=4000,
            expected_completion_date=date(2026, 5, 21),
            notes=SEED_NOTES,
        ),
    )
    for payload in [
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.stitching,
            allocation_id=dbl_stc_a.id,
            entry_date=date(2026, 5, 9),
            completed_today=3500,
            approved_today=3400,
            rejected_today=50,
            repair_today=30,
            alter_today=20,
            moved_to_next_stage_today=3400,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.stitching,
            allocation_id=dbl_stc_b.id,
            entry_date=date(2026, 5, 10),
            completed_today=3000,
            approved_today=2940,
            rejected_today=20,
            repair_today=20,
            alter_today=20,
            moved_to_next_stage_today=2600,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.stitching,
            allocation_id=dbl_stc_c.id,
            entry_date=date(2026, 5, 11),
            completed_today=2000,
            approved_today=1980,
            rejected_today=10,
            repair_today=5,
            alter_today=5,
            moved_to_next_stage_today=1800,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.size_inspection,
            allocation_id=None,
            entry_date=date(2026, 5, 12),
            completed_today=6000,
            approved_today=5800,
            rejected_today=80,
            repair_today=70,
            alter_today=50,
            moved_to_next_stage_today=5600,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.quality_check,
            allocation_id=None,
            entry_date=date(2026, 5, 13),
            completed_today=5000,
            approved_today=4800,
            rejected_today=100,
            repair_today=50,
            alter_today=50,
            moved_to_next_stage_today=4500,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.packing,
            allocation_id=None,
            entry_date=date(2026, 5, 14),
            completed_today=4200,
            approved_today=4100,
            rejected_today=50,
            repair_today=25,
            alter_today=25,
            moved_to_next_stage_today=3500,
            remarks=SEED_NOTES,
        ),
    ]:
        await record_stage_progress(db, payload)

    # PIL-2026-001 smooth completion
    sm = await _stage_map(db, pos["PIL-2026-001"].id)
    stage_maps["PIL-2026-001"] = sm
    pil_cut = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.cutting].id,
            contractor_id=contractors["Cutting Contractor A"].id,
            issued_qty=20000,
            expected_completion_date=date(2026, 5, 12),
            notes=SEED_NOTES,
        ),
    )
    await record_stage_progress(
        db,
        StageProgressCreate(
            purchase_order_id=pos["PIL-2026-001"].id,
            stage=StageName.cutting,
            allocation_id=pil_cut.id,
            entry_date=date(2026, 5, 8),
            completed_today=20000,
            approved_today=20000,
            rejected_today=0,
            repair_today=0,
            alter_today=0,
            moved_to_next_stage_today=20000,
            remarks=SEED_NOTES,
        ),
    )
    for stage_name, entry_day in [
        (StageName.stitching, date(2026, 5, 9)),
        (StageName.size_inspection, date(2026, 5, 10)),
        (StageName.quality_check, date(2026, 5, 11)),
        (StageName.packing, date(2026, 5, 12)),
    ]:
        await record_stage_progress(
            db,
            StageProgressCreate(
                purchase_order_id=pos["PIL-2026-001"].id,
                stage=stage_name,
                allocation_id=None,
                entry_date=entry_day,
                completed_today=20000,
                approved_today=20000,
                rejected_today=0,
                repair_today=0,
                alter_today=0,
                moved_to_next_stage_today=20000,
                remarks=SEED_NOTES,
            ),
        )

    # SGL-2026-001 high rejection scenario
    sm = await _stage_map(db, pos["SGL-2026-001"].id)
    stage_maps["SGL-2026-001"] = sm
    sgl_cut = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.cutting].id,
            contractor_id=contractors["Cutting Contractor B"].id,
            issued_qty=10000,
            expected_completion_date=date(2026, 5, 13),
            notes=SEED_NOTES,
        ),
    )
    for payload in [
        StageProgressCreate(
            purchase_order_id=pos["SGL-2026-001"].id,
            stage=StageName.cutting,
            allocation_id=sgl_cut.id,
            entry_date=date(2026, 5, 8),
            completed_today=9000,
            approved_today=8000,
            rejected_today=700,
            repair_today=150,
            alter_today=150,
            moved_to_next_stage_today=8000,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["SGL-2026-001"].id,
            stage=StageName.stitching,
            allocation_id=None,
            entry_date=date(2026, 5, 9),
            completed_today=5000,
            approved_today=4600,
            rejected_today=200,
            repair_today=100,
            alter_today=100,
            moved_to_next_stage_today=4200,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["SGL-2026-001"].id,
            stage=StageName.size_inspection,
            allocation_id=None,
            entry_date=date(2026, 5, 10),
            completed_today=3500,
            approved_today=3200,
            rejected_today=120,
            repair_today=100,
            alter_today=80,
            moved_to_next_stage_today=2900,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["SGL-2026-001"].id,
            stage=StageName.quality_check,
            allocation_id=None,
            entry_date=date(2026, 5, 11),
            completed_today=2600,
            approved_today=2350,
            rejected_today=150,
            repair_today=60,
            alter_today=40,
            moved_to_next_stage_today=2000,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["SGL-2026-001"].id,
            stage=StageName.packing,
            allocation_id=None,
            entry_date=date(2026, 5, 12),
            completed_today=1800,
            approved_today=1650,
            rejected_today=80,
            repair_today=40,
            alter_today=30,
            moved_to_next_stage_today=1500,
            remarks=SEED_NOTES,
        ),
    ]:
        await record_stage_progress(db, payload)

    # KNG-2026-001 contractor delay scenario
    sm = await _stage_map(db, pos["KNG-2026-001"].id)
    stage_maps["KNG-2026-001"] = sm
    kng_cut = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.cutting].id,
            contractor_id=contractors["Cutting Contractor A"].id,
            issued_qty=9000,
            expected_completion_date=date(2026, 5, 12),
            notes=SEED_NOTES,
        ),
    )
    await record_stage_progress(
        db,
        StageProgressCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            stage=StageName.cutting,
            allocation_id=kng_cut.id,
            entry_date=date(2026, 5, 8),
            completed_today=7000,
            approved_today=7000,
            rejected_today=0,
            repair_today=0,
            alter_today=0,
            moved_to_next_stage_today=7000,
            remarks=SEED_NOTES,
        ),
    )
    sm = await _stage_map(db, pos["KNG-2026-001"].id)
    stage_maps["KNG-2026-001"] = sm
    kng_stc = await allocate_contractor(
        db,
        ContractorAllocationCreate(
            stage_summary_id=sm[StageName.stitching].id,
            contractor_id=contractors["Stitching Contractor B"].id,
            issued_qty=7000,
            expected_completion_date=date(2026, 5, 5),
            notes=f"{SEED_NOTES} delayed contractor",
        ),
    )
    for payload in [
        StageProgressCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            stage=StageName.stitching,
            allocation_id=kng_stc.id,
            entry_date=date(2026, 5, 9),
            completed_today=3000,
            approved_today=2600,
            rejected_today=200,
            repair_today=100,
            alter_today=100,
            moved_to_next_stage_today=2000,
            delay_days=2,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            stage=StageName.size_inspection,
            allocation_id=None,
            entry_date=date(2026, 5, 10),
            completed_today=1500,
            approved_today=1400,
            rejected_today=50,
            repair_today=30,
            alter_today=20,
            moved_to_next_stage_today=1200,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            stage=StageName.quality_check,
            allocation_id=None,
            entry_date=date(2026, 5, 11),
            completed_today=1200,
            approved_today=1100,
            rejected_today=50,
            repair_today=30,
            alter_today=20,
            moved_to_next_stage_today=1000,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            stage=StageName.packing,
            allocation_id=None,
            entry_date=date(2026, 5, 12),
            completed_today=900,
            approved_today=850,
            rejected_today=20,
            repair_today=20,
            alter_today=10,
            moved_to_next_stage_today=800,
            remarks=SEED_NOTES,
        ),
    ]:
        await record_stage_progress(db, payload)

    # FIT-2026-001 packing pending scenario
    sm = await _stage_map(db, pos["FIT-2026-001"].id)
    stage_maps["FIT-2026-001"] = sm
    for payload in [
        StageProgressCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            stage=StageName.cutting,
            allocation_id=None,
            entry_date=date(2026, 5, 8),
            completed_today=4000,
            approved_today=3800,
            rejected_today=80,
            repair_today=70,
            alter_today=50,
            moved_to_next_stage_today=3500,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            stage=StageName.stitching,
            allocation_id=None,
            entry_date=date(2026, 5, 9),
            completed_today=3000,
            approved_today=2800,
            rejected_today=80,
            repair_today=70,
            alter_today=50,
            moved_to_next_stage_today=2500,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            stage=StageName.size_inspection,
            allocation_id=None,
            entry_date=date(2026, 5, 10),
            completed_today=2300,
            approved_today=2200,
            rejected_today=40,
            repair_today=30,
            alter_today=30,
            moved_to_next_stage_today=2000,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            stage=StageName.quality_check,
            allocation_id=None,
            entry_date=date(2026, 5, 11),
            completed_today=1800,
            approved_today=1650,
            rejected_today=70,
            repair_today=50,
            alter_today=30,
            moved_to_next_stage_today=1400,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            stage=StageName.packing,
            allocation_id=None,
            entry_date=date(2026, 5, 12),
            completed_today=1300,
            approved_today=1200,
            rejected_today=50,
            repair_today=30,
            alter_today=20,
            moved_to_next_stage_today=1000,
            remarks=SEED_NOTES,
        ),
    ]:
        await record_stage_progress(db, payload)

    # PIL-2026-002 near completion but not dispatched yet
    for payload in [
        StageProgressCreate(
            purchase_order_id=pos["PIL-2026-002"].id,
            stage=StageName.cutting,
            allocation_id=None,
            entry_date=date(2026, 5, 8),
            completed_today=10000,
            approved_today=9800,
            rejected_today=80,
            repair_today=60,
            alter_today=60,
            moved_to_next_stage_today=9800,
            remarks=SEED_NOTES,
        ),
        StageProgressCreate(
            purchase_order_id=pos["PIL-2026-002"].id,
            stage=StageName.stitching,
            allocation_id=None,
            entry_date=date(2026, 5, 9),
            completed_today=9000,
            approved_today=8700,
            rejected_today=120,
            repair_today=90,
            alter_today=90,
            moved_to_next_stage_today=8200,
            remarks=SEED_NOTES,
        ),
    ]:
        await record_stage_progress(db, payload)

    # Quality failure lifecycle entries
    sm = await _stage_map(db, pos["DBL-2026-001"].id)
    await record_quality_failure(
        db,
        QualityFailureCreate(
            stage_summary_id=sm[StageName.quality_check].id,
            allocation_id=None,
            failed_qty=120,
            resolved_qty=80,
            action=QualityAction.repair_in_factory,
            reason="Stitch density mismatch",
            resolution="Sent to in-house repair line",
            action_date=TODAY,
        ),
    )
    sm = await _stage_map(db, pos["KNG-2026-001"].id)
    await record_quality_failure(
        db,
        QualityFailureCreate(
            stage_summary_id=sm[StageName.stitching].id,
            allocation_id=None,
            failed_qty=200,
            resolved_qty=50,
            action=QualityAction.return_to_contractor,
            reason="Uneven stitch pattern",
            resolution="Returned batch to contractor B",
            action_date=TODAY,
        ),
    )
    sm = await _stage_map(db, pos["SGL-2026-001"].id)
    await record_quality_failure(
        db,
        QualityFailureCreate(
            stage_summary_id=sm[StageName.cutting].id,
            allocation_id=None,
            failed_qty=300,
            resolved_qty=300,
            action=QualityAction.reject,
            reason="Fabric tear and inaccurate cut",
            resolution="Rejected and recut planned",
            action_date=TODAY,
        ),
    )

    # QC entries
    await create_qc_inspection(
        db,
        QCInspectionCreate(
            purchase_order_id=pos["PIL-2026-001"].id,
            stage=StageName.quality_check,
            inspected_qty=5000,
            size_ok=True,
            stitching_ok=True,
            shape_ok=True,
            fabric_defect_found=False,
            passed_qty=5000,
            failed_qty=0,
            repair_qty=0,
            alteration_qty=0,
            rejected_qty=0,
            inspected_by=user.id,
            inspection_date=TODAY,
            status=StageStatus.completed,
            remarks=SEED_NOTES,
        ),
    )
    await create_qc_inspection(
        db,
        QCInspectionCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.size_inspection,
            inspected_qty=3000,
            size_ok=False,
            stitching_ok=True,
            shape_ok=True,
            fabric_defect_found=False,
            defect_notes="Size variance in edge fold",
            passed_qty=2700,
            failed_qty=300,
            repair_qty=100,
            alteration_qty=100,
            rejected_qty=100,
            inspected_by=user.id,
            inspection_date=TODAY,
            status=StageStatus.in_progress,
            remarks=SEED_NOTES,
        ),
    )
    await create_qc_inspection(
        db,
        QCInspectionCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            stage=StageName.stitching,
            inspected_qty=1500,
            size_ok=True,
            stitching_ok=False,
            shape_ok=True,
            fabric_defect_found=True,
            defect_notes="Skipped stitches detected",
            passed_qty=1300,
            failed_qty=200,
            repair_qty=120,
            alteration_qty=40,
            rejected_qty=40,
            inspected_by=user.id,
            inspection_date=TODAY,
            status=StageStatus.in_progress,
            remarks=SEED_NOTES,
        ),
    )
    await create_qc_inspection(
        db,
        QCInspectionCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            stage=StageName.quality_check,
            inspected_qty=1200,
            size_ok=True,
            stitching_ok=True,
            shape_ok=False,
            fabric_defect_found=False,
            defect_notes="Shape tolerance issue",
            passed_qty=1050,
            failed_qty=150,
            repair_qty=100,
            alteration_qty=20,
            rejected_qty=30,
            inspected_by=user.id,
            inspection_date=TODAY,
            status=StageStatus.in_progress,
            remarks=SEED_NOTES,
        ),
    )
    await create_qc_inspection(
        db,
        QCInspectionCreate(
            purchase_order_id=pos["SGL-2026-001"].id,
            stage=StageName.quality_check,
            inspected_qty=2000,
            size_ok=True,
            stitching_ok=False,
            shape_ok=True,
            fabric_defect_found=False,
            defect_notes="Panel alignment issue",
            passed_qty=1700,
            failed_qty=300,
            repair_qty=80,
            alteration_qty=70,
            rejected_qty=150,
            inspected_by=user.id,
            inspection_date=TODAY,
            status=StageStatus.in_progress,
            remarks=SEED_NOTES,
        ),
    )

    # Packing analysis / daily packing output
    for payload in [
        PackingOutputCreate(
            purchase_order_id=pos["PIL-2026-001"].id,
            output_date=TODAY,
            worker_count=25,
            packed_qty=20000,
            pending_qty=0,
            daily_target=d("1000"),
            required_workers=d("20"),
            blocker_reason=None,
            updated_by=user.id,
            assigned_to=user.id,
            responsible_role="packing_supervisor",
            remarks=SEED_NOTES,
        ),
        PackingOutputCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            output_date=TODAY,
            worker_count=4,
            packed_qty=1200,
            pending_qty=3800,
            daily_target=d("950"),
            required_workers=d("8"),
            blocker_reason=None,
            updated_by=user.id,
            assigned_to=user.id,
            responsible_role="packing_supervisor",
            remarks=SEED_NOTES,
        ),
        PackingOutputCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            output_date=TODAY,
            worker_count=3,
            packed_qty=850,
            pending_qty=8200,
            daily_target=d("1200"),
            required_workers=d("10"),
            blocker_reason="Stitching output from contractor B is low",
            updated_by=user.id,
            assigned_to=user.id,
            responsible_role="packing_supervisor",
            remarks=SEED_NOTES,
        ),
    ]:
        await update_packing_output(db, payload)

    # Fabric issue to cutting
    inv_result = await db.execute(select(FabricInventory))
    inventories = inv_result.scalars().all()
    inv_map = {(item.fabric_type, item.color, str(item.gsm), str(item.width)): item for item in inventories}
    for po_number, issued in [
        ("DBL-2026-001", d("21000")),
        ("SGL-2026-001", d("12000")),
        ("PIL-2026-001", d("13000")),
    ]:
        po_seed = next(row for row in PO_SEEDS if row.po_number == po_number)
        inv = inv_map.get((po_seed.fabric_type, po_seed.color, str(po_seed.gsm), str(po_seed.width)))
        if inv is None:
            continue
        db.add(
            FabricIssueToCutting(
                purchase_order_id=pos[po_number].id,
                fabric_inventory_id=inv.id,
                fabric_receipt_id=None,
                issued_meters=issued,
                issued_rolls=None,
                issued_by=user.id,
                received_by=user.id,
                issue_date=TODAY,
                remarks=SEED_NOTES,
                assigned_to=user.id,
                responsible_role="store_manager",
                completed_by=user.id,
                completed_at=datetime.now(timezone.utc),
            )
        )
    await db.commit()

    # Cutting wastage analysis
    await upsert_cutting_analysis(
        db,
        CuttingAnalysisCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            planned_cut_size="78 x 98 inch",
            actual_cut_size="78 x 98 inch",
            planned_consumption_m=d("36000"),
            actual_consumption_m=d("36240"),
            planned_wastage_m=d("36"),
            actual_wastage_m=d("96"),
            reason_for_difference="Extra edge correction due to print alignment",
            cutting_supervisor_id=user.id,
            assigned_to=user.id,
            responsible_role="cutting_supervisor",
            completed_by=user.id,
            completed_at=datetime.now(timezone.utc),
            remarks=SEED_NOTES,
        ),
    )

    # Stage-wise costing
    for payload in [
        StageCostEntryCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.cutting,
            contractor_id=contractors["Cutting Contractor A"].id,
            qty=12000,
            rate_per_piece=d("3.50"),
            manual_cost=None,
            remarks=SEED_NOTES,
        ),
        StageCostEntryCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            stage=StageName.stitching,
            contractor_id=contractors["Stitching Contractor A"].id,
            qty=8500,
            rate_per_piece=d("5.75"),
            manual_cost=None,
            remarks=SEED_NOTES,
        ),
        StageCostEntryCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            stage=StageName.packing,
            contractor_id=None,
            qty=1200,
            rate_per_piece=None,
            manual_cost=d("8400.00"),
            remarks=SEED_NOTES,
        ),
    ]:
        await create_stage_cost_entry(db, payload)

    # Dispatch loads
    for payload in [
        DispatchLoadCreate(
            purchase_order_id=pos["PIL-2026-001"].id,
            load_number="PIL001-L1",
            shipped_qty=20000,
            vehicle_type="Truck",
            vehicle_identifier="HR55-1001",
            expected_piece_capacity=22000,
            actual_loaded_pieces=20000,
            cbm_capacity=d("70"),
            cbm_used=d("62"),
            cost_type=DispatchCostType.invoice_percent,
            invoice_value=d("900000"),
            dispatch_percent=d("1.80"),
            cbm_value=None,
            cbm_rate=None,
            manual_cost=None,
            vehicle_cost=None,
            shipped_at=TODAY,
            transporter_name="Haryana Transport",
            destination="Jaipur DC",
            tracking_reference="TRK-PIL-001",
            assigned_to=user.id,
            responsible_role="dispatch_manager",
            completed_by=user.id,
            completed_at=datetime.now(timezone.utc),
            remarks=SEED_NOTES,
        ),
        DispatchLoadCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            load_number="DBL001-L1",
            shipped_qty=2500,
            vehicle_type="Mini Truck",
            vehicle_identifier="DL1L-2201",
            expected_piece_capacity=3000,
            actual_loaded_pieces=2500,
            cbm_capacity=d("25"),
            cbm_used=d("18"),
            cost_type=DispatchCostType.manual,
            invoice_value=None,
            dispatch_percent=None,
            cbm_value=None,
            cbm_rate=None,
            manual_cost=d("9000"),
            vehicle_cost=None,
            shipped_at=TODAY,
            transporter_name="Delhi Cargo Movers",
            destination="Noida Hub",
            tracking_reference="TRK-DBL-001-A",
            assigned_to=user.id,
            responsible_role="dispatch_manager",
            completed_by=user.id,
            completed_at=datetime.now(timezone.utc),
            remarks=SEED_NOTES,
        ),
        DispatchLoadCreate(
            purchase_order_id=pos["DBL-2026-001"].id,
            load_number="DBL001-L2",
            shipped_qty=500,
            vehicle_type="Pickup",
            vehicle_identifier="HR26-7788",
            expected_piece_capacity=700,
            actual_loaded_pieces=500,
            cbm_capacity=d("8"),
            cbm_used=d("5"),
            cost_type=DispatchCostType.vehicle_capacity,
            invoice_value=None,
            dispatch_percent=None,
            cbm_value=None,
            cbm_rate=None,
            manual_cost=None,
            vehicle_cost=d("3000"),
            shipped_at=TODAY,
            transporter_name="Haryana Transport",
            destination="Gurugram Hub",
            tracking_reference="TRK-DBL-001-B",
            assigned_to=user.id,
            responsible_role="dispatch_manager",
            completed_by=user.id,
            completed_at=datetime.now(timezone.utc),
            remarks=SEED_NOTES,
        ),
        DispatchLoadCreate(
            purchase_order_id=pos["SGL-2026-001"].id,
            load_number="SGL001-L1",
            shipped_qty=1200,
            vehicle_type="Mini Truck",
            vehicle_identifier="UP16-4422",
            expected_piece_capacity=1500,
            actual_loaded_pieces=1200,
            cbm_capacity=d("10"),
            cbm_used=d("7"),
            cost_type=DispatchCostType.invoice_percent,
            invoice_value=d("162000"),
            dispatch_percent=d("2.00"),
            cbm_value=None,
            cbm_rate=None,
            manual_cost=None,
            vehicle_cost=None,
            shipped_at=TODAY,
            transporter_name="Delhi Cargo Movers",
            destination="Lucknow",
            tracking_reference="TRK-SGL-001",
            assigned_to=user.id,
            responsible_role="dispatch_manager",
            completed_by=user.id,
            completed_at=datetime.now(timezone.utc),
            remarks=SEED_NOTES,
        ),
        DispatchLoadCreate(
            purchase_order_id=pos["KNG-2026-001"].id,
            load_number="KNG001-L1",
            shipped_qty=700,
            vehicle_type="Container",
            vehicle_identifier="RJ14-8899",
            expected_piece_capacity=1200,
            actual_loaded_pieces=700,
            cbm_capacity=d("30"),
            cbm_used=d("12.5"),
            cost_type=DispatchCostType.cbm,
            invoice_value=None,
            dispatch_percent=None,
            cbm_value=d("12.5"),
            cbm_rate=d("130"),
            manual_cost=None,
            vehicle_cost=None,
            shipped_at=TODAY,
            transporter_name="Haryana Transport",
            destination="Bhopal",
            tracking_reference="TRK-KNG-001",
            assigned_to=user.id,
            responsible_role="dispatch_manager",
            completed_by=user.id,
            completed_at=datetime.now(timezone.utc),
            remarks=SEED_NOTES,
        ),
        DispatchLoadCreate(
            purchase_order_id=pos["FIT-2026-001"].id,
            load_number="FIT001-L1",
            shipped_qty=900,
            vehicle_type="Mini Truck",
            vehicle_identifier="HR38-5012",
            expected_piece_capacity=1200,
            actual_loaded_pieces=900,
            cbm_capacity=d("12"),
            cbm_used=d("8"),
            cost_type=DispatchCostType.manual,
            invoice_value=None,
            dispatch_percent=None,
            cbm_value=None,
            cbm_rate=None,
            manual_cost=d("4200"),
            vehicle_cost=None,
            shipped_at=TODAY,
            transporter_name="Delhi Cargo Movers",
            destination="Indore",
            tracking_reference="TRK-FIT-001",
            assigned_to=user.id,
            responsible_role="dispatch_manager",
            completed_by=user.id,
            completed_at=datetime.now(timezone.utc),
            remarks=SEED_NOTES,
        ),
    ]:
        await create_dispatch_load(db, payload)
        dispatch_count += 1

    # Reminders (task-like)
    reminder_payloads = [
        (pos["DBL-2026-003"].id, ReminderType.followup_due, "Mill follow-up due", "Follow up with Surya Mills for committed lot.", TODAY, ReminderPriority.medium),
        (pos["KNG-2026-002"].id, ReminderType.fabric_verification_pending, "Fabric verification pending", "Verification is pending for received fabric lot.", TODAY, ReminderPriority.high),
        (pos["DBL-2026-001"].id, ReminderType.cutting_due, "Cutting due", "Close balance cutting qty and release all pieces.", TODAY, ReminderPriority.medium),
        (pos["KNG-2026-001"].id, ReminderType.stitching_due, "Stitching due", "Stitching contractor has pending delayed balance.", TODAY, ReminderPriority.high),
        (pos["SGL-2026-001"].id, ReminderType.qc_pending, "QC pending", "QC action is pending on rejected batch.", TODAY, ReminderPriority.high),
        (pos["FIT-2026-001"].id, ReminderType.packing_due, "Packing due", "Increase packers to avoid dispatch miss.", TODAY, ReminderPriority.high),
        (pos["DBL-2026-001"].id, ReminderType.dispatch_due, "Dispatch due", "Next dispatch load should be planned today.", TODAY, ReminderPriority.high),
        (pos["FIT-2026-002"].id, ReminderType.mill_delivery_overdue, "Mill delivery overdue", "Committed mill delivery date is missed.", TODAY, ReminderPriority.critical),
        (pos["DBL-2026-003"].id, ReminderType.mill_delivery_due, "Mill delivery due", "Mill delivery due in coming days.", date(2026, 5, 20), ReminderPriority.medium),
    ]
    for po_id, rtype, title, message, due_date, priority in reminder_payloads:
        db.add(
            Reminder(
                purchase_order_id=po_id,
                reminder_type=rtype,
                title=title,
                message=message,
                due_date=due_date,
                assigned_to=user.id,
                priority=priority,
                status=ReminderStatus.open,
            )
        )
    await db.commit()

    # Additional explicit alerts for nuanced dashboard cards
    manual_alerts = [
        (pos["KNG-2026-002"].id, AlertType.stage_delay, AlertPriority.high, "Fabric verification pending", "Received fabric is awaiting verification and blocks cutting."),
        (pos["FIT-2026-002"].id, AlertType.stage_delay, AlertPriority.critical, "Mill delivery overdue", "Committed mill date missed; shortage still open."),
        (pos["DBL-2026-001"].id, AlertType.shipment_risk, AlertPriority.medium, "Dispatch pending", "PO has packed stock but pending dispatch loads."),
    ]
    for po_id, atype, priority, title, message in manual_alerts:
        db.add(Alert(purchase_order_id=po_id, alert_type=atype, priority=priority, title=title, message=message))
    await db.commit()

    # Automated alerts from system logic
    await generate_alerts(db)

    # Capacity and underutilization signals
    for product_type in ProductType:
        for stage, daily, workers in [
            (CapacityStage.cutting, 2800, 12),
            (CapacityStage.stitching, 2300, 18),
            (CapacityStage.packing, 1700, 10),
        ]:
            await create_capacity_profile(
                db,
                CapacityProfileCreate(
                    product_type=product_type,
                    stage=stage,
                    daily_capacity_qty=daily,
                    worker_count=workers,
                    overtime_allowed=True,
                    include_sunday=False,
                    effective_from=date(2026, 5, 1),
                    is_active=True,
                    assigned_to=user.id,
                    responsible_role="planner",
                    completed_by=user.id,
                    completed_at=datetime.now(timezone.utc),
                    remarks=SEED_NOTES,
                ),
            )
    await detect_underutilization(db, CapacityStage.cutting, threshold_days=5, as_of=TODAY)
    await detect_underutilization(db, CapacityStage.stitching, threshold_days=5, as_of=TODAY)
    await detect_underutilization(db, CapacityStage.packing, threshold_days=5, as_of=TODAY)

    return dispatch_count


async def summarize(db: AsyncSession) -> dict[str, int]:
    po_numbers = [row.po_number for row in PO_SEEDS]
    pos_result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.po_number.in_(po_numbers)))
    pos = list(pos_result.scalars().all())
    po_ids = [po.id for po in pos]

    ready = 0
    shortage = 0
    for po in pos:
        await db.refresh(po, attribute_names=["fabric_plan"])
        if po.fabric_plan and po.fabric_plan.status == FabricPlanStatus.fabric_ready:
            ready += 1
        elif po.fabric_plan and po.fabric_plan.status == FabricPlanStatus.shortage:
            shortage += 1

    product_count = (
        await db.execute(select(Product).where(Product.product_category == SEED_PRODUCT_CATEGORY))
    ).scalars().all()
    contractor_count = (
        await db.execute(select(Contractor).where(Contractor.name.in_([name for name, _ in CONTRACTOR_SEEDS])))
    ).scalars().all()
    mill_req_count = (
        await db.execute(select(MillOrderRequirement).where(MillOrderRequirement.purchase_order_id.in_(po_ids)))
    ).scalars().all()
    alert_count = (await db.execute(select(Alert).where(Alert.purchase_order_id.in_(po_ids)))).scalars().all()
    reminder_count = (await db.execute(select(Reminder).where(Reminder.purchase_order_id.in_(po_ids)))).scalars().all()
    dispatch_count = (await db.execute(select(DispatchLoad).where(DispatchLoad.purchase_order_id.in_(po_ids)))).scalars().all()
    return {
        "total_pos_created": len(pos),
        "total_products_created": len(product_count),
        "total_contractors_created": len(contractor_count),
        "fabric_ready_count": ready,
        "fabric_shortage_count": shortage,
        "mill_requirements_created": len(mill_req_count),
        "alerts_created": len(alert_count),
        "reminders_created": len(reminder_count),
        "dispatch_loads_created": len(dispatch_count),
    }


async def run_seed() -> None:
    await ensure_schema()
    async with AsyncSessionLocal() as db:
        await reset_seed_data(db)
        user = await ensure_seed_user(db)
        products = await create_seed_products(db)
        await create_seed_inventory(db, products)
        pos = await create_seed_pos(db, user, products)
        await create_po_drafts(db, user)
        requirements = await create_shortages_mill_requirements_and_reminders(db, pos, user)
        await create_mill_orders_followups_and_receipts(db, pos, requirements, user)
        contractors = await create_seed_contractors(db)
        await create_allocations_progress_qc_dispatch(db, pos, contractors, user)

        # Ensure at least one explicitly delayed PO status for dashboard variety.
        delayed_po = pos["KNG-2026-001"]
        delayed_po.status = POStatus.delayed
        await db.commit()

        summary = await summarize(db)
        print("\nSeed completed successfully.")
        for key, value in summary.items():
            print(f"- {key}: {value}")


if __name__ == "__main__":
    asyncio.run(run_seed())
