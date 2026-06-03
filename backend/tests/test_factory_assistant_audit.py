from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.api.v1.routes.voice_ws import _resolve_owner
from app.core.security import create_access_token, hash_password
from app.models.enums import POStatus, UserRole
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.services.dashboard_service import get_owner_dashboard
from app.services.operational_backfill import ensure_all_operational_data
from app.services.pdf_reports.report_schemas import ReportGenerateRequest
from app.services.pdf_reports.report_service import ReportService
from app.services.quotation_service import build_po_quotation
from app.services.voice.artifacts import artifacts_scope
from app.services.voice.factory_queries import answer_factory_question


@pytest_asyncio.fixture
async def audit_db(tmp_path):
    from app import models  # noqa: F401  # register all SQLAlchemy models

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        product = Product(
            product_name="109",
            product_category="category",
            size="140x215",
            design="Multi-fabric",
            color="Multi",
            fabric_type="Cotton",
            gsm=Decimal("100"),
            width=Decimal("1.42"),
            per_piece_fabric_usage_m=Decimal("2.000"),
            wastage_percent=Decimal("0"),
        )
        db.add(product)
        await db.flush()
        db.add_all(
            [
                ProductFabricLine(
                    product_id=product.id,
                    fabric_code="SHORT-FLORA",
                    pieces=0,
                    pieces_in_stock=0,
                    pieces_short=0,
                    stock_status="unknown",
                    per_piece_meters=Decimal("2.000"),
                    stock_meters=Decimal("50.000"),
                ),
                ProductFabricLine(
                    product_id=product.id,
                    fabric_code="READY-FLORA",
                    pieces=0,
                    pieces_in_stock=0,
                    pieces_short=0,
                    stock_status="unknown",
                    per_piece_meters=Decimal("2.000"),
                    stock_meters=Decimal("300.000"),
                ),
            ]
        )
        db.add_all(
            [
                PurchaseOrder(
                    po_number="109-SHORT-FLORA-JUNE",
                    product_id=product.id,
                    order_quantity_pcs=100,
                    mrp=Decimal("109"),
                    selling_price=Decimal("150"),
                    order_date=date(2026, 6, 1),
                    promise_delivery_date=date(2026, 6, 30),
                    status=POStatus.fabric_check_pending,
                    design_name_snapshot="SHORT-FLORA",
                    design_code_snapshot="SHORT-FLORA",
                    notes="audit fixture",
                ),
                PurchaseOrder(
                    po_number="109-READY-FLORA-JUNE",
                    product_id=product.id,
                    order_quantity_pcs=100,
                    mrp=Decimal("109"),
                    selling_price=Decimal("150"),
                    order_date=date(2026, 6, 1),
                    promise_delivery_date=date(2026, 6, 30),
                    status=POStatus.fabric_check_pending,
                    design_name_snapshot="READY-FLORA",
                    design_code_snapshot="READY-FLORA",
                    notes="audit fixture",
                ),
                PurchaseOrder(
                    po_number="109-MAY-COMPLETE",
                    product_id=product.id,
                    order_quantity_pcs=50,
                    mrp=Decimal("109"),
                    selling_price=Decimal("150"),
                    order_date=date(2026, 5, 1),
                    promise_delivery_date=date(2026, 5, 31),
                    actual_delivery_date=date(2026, 5, 28),
                    status=POStatus.completed,
                    design_name_snapshot="READY-FLORA",
                    design_code_snapshot="READY-FLORA",
                    notes="audit fixture",
                ),
            ]
        )
        await db.commit()
        yield db
    await engine.dispose()


@pytest.mark.asyncio
async def test_june_po_filtering_and_end_of_june_answer_use_database(audit_db) -> None:
    answer = await answer_factory_question(audit_db, "Which June POs must be dispatched by the end of June?")
    assert answer is not None
    assert "June POs due by June 30: 2 found" in answer.answer
    assert "109-SHORT-FLORA-JUNE" in answer.answer
    assert "109-READY-FLORA-JUNE" in answer.answer
    assert "109-MAY-COMPLETE" not in answer.answer


@pytest.mark.asyncio
async def test_fabric_shortage_backfill_and_mill_requirement(audit_db) -> None:
    await ensure_all_operational_data(audit_db)
    rows = (await audit_db.execute(select(PurchaseOrder).order_by(PurchaseOrder.po_number))).scalars().all()
    by_number = {row.po_number: row for row in rows}
    short_po = by_number["109-SHORT-FLORA-JUNE"]
    ready_po = by_number["109-READY-FLORA-JUNE"]
    await audit_db.refresh(short_po, attribute_names=["fabric_plan", "mill_order_requirements", "stage_summaries"])
    await audit_db.refresh(ready_po, attribute_names=["fabric_plan", "stage_summaries"])
    assert short_po.fabric_plan.shortage_m == Decimal("150.000")
    assert short_po.status == POStatus.shortage
    assert short_po.mill_order_requirements
    assert ready_po.fabric_plan.shortage_m == Decimal("0.000")
    assert ready_po.status == POStatus.fabric_ready
    cutting = next(stage for stage in ready_po.stage_summaries if stage.stage.value == "cutting")
    assert cutting.pending_qty == 100


@pytest.mark.asyncio
async def test_assistant_answers_shortage_stage_and_contractor_without_hallucination(audit_db) -> None:
    shortage = await answer_factory_question(audit_db, "Which June POs have fabric shortage?")
    assert shortage is not None
    assert "109-SHORT-FLORA-JUNE" in shortage.answer
    assert "short 150.0 m" in shortage.answer

    stage = await answer_factory_question(audit_db, "Which POs are stuck in cutting?")
    assert stage is not None
    assert "109-READY-FLORA-JUNE" in stage.answer

    contractor = await answer_factory_question(audit_db, "Which contractor is working on PO 109-READY-FLORA-JUNE?")
    assert contractor is not None
    assert "No contractor allocation is recorded" in contractor.answer


@pytest.mark.asyncio
async def test_quotation_uses_recorded_po_price_and_flags_missing_fields(audit_db) -> None:
    quotation = await build_po_quotation(audit_db, "109-SHORT-FLORA-JUNE")
    assert quotation.quantity_pcs == 100
    assert quotation.unit_price == Decimal("150.00")
    assert quotation.total_amount == Decimal("15000.00")
    assert {"buyer_name", "tax_rate"}.issubset(set(quotation.missing_fields))


@pytest.mark.asyncio
async def test_pdf_generation_and_assistant_artifact(audit_db, tmp_path) -> None:
    service = ReportService(audit_db, reports_dir=tmp_path)
    request = await service.create_request(
        ReportGenerateRequest(report_type="generate_pdf_june_dispatch", filters={"month": 6, "year": 2026}),
        requested_by=None,
    )
    generated = await service.generate_report(request.id)
    assert generated.status.value == "completed"
    assert generated.file_path
    assert "generate_pdf_june_dispatch" in generated.file_path

    with artifacts_scope() as artifacts:
        answer = await answer_factory_question(audit_db, "Generate fabric shortage PDF")
    assert answer is not None
    assert "Fabric Shortage Report is ready" in answer.answer
    assert artifacts and artifacts[0]["type"] == "pdf"


@pytest.mark.asyncio
async def test_dashboard_aggregation_matches_backfilled_database(audit_db) -> None:
    dashboard = await get_owner_dashboard(audit_db)
    assert dashboard.active_pos == 2
    assert dashboard.fabric_shortages == 1
    assert dashboard.pending_dispatch == 0
    short_row = next(row for row in dashboard.purchase_orders if row.po_number == "109-SHORT-FLORA-JUNE")
    assert short_row.fabric_shortage_m == 150.0


@pytest.mark.asyncio
async def test_voice_ws_owner_resolution_uses_current_role_model(audit_db) -> None:
    owner = User(
        full_name="Owner",
        email="owner-audit@example.com",
        password_hash=hash_password("OwnerAudit@2026"),
        role=UserRole.owner,
        is_active=True,
    )
    manager = User(
        full_name="Manager",
        email="manager-audit@example.com",
        password_hash=hash_password("ManagerAudit@2026"),
        role=UserRole.manager,
        is_active=True,
    )
    audit_db.add_all([owner, manager])
    await audit_db.commit()
    await audit_db.refresh(owner)
    await audit_db.refresh(manager)

    assert await _resolve_owner(create_access_token(owner.id), audit_db) == owner
    assert await _resolve_owner(create_access_token(manager.id), audit_db) is None
