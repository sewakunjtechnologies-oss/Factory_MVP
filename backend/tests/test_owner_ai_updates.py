from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.contractor import Contractor
from app.models.enums import ContractorType, POStatus, StageName, StageStatus
from app.models.fabric import FabricReceipt
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageSummary
from app.services.voice.factory_queries import _PENDING_WRITE, answer_factory_question


@pytest_asyncio.fixture
async def owner_ai_db(tmp_path):
    from app import models  # noqa: F401  # register all SQLAlchemy models

    _PENDING_WRITE.clear()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'owner_ai.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        product = Product(
            product_name="109",
            product_category="category",
            size="140x215",
            design="Owner AI",
            color="Multi",
            fabric_type="Cotton",
            gsm=Decimal("100"),
            width=Decimal("1.42"),
            per_piece_fabric_usage_m=Decimal("2.000"),
            wastage_percent=Decimal("0"),
        )
        db.add(product)
        await db.flush()
        db.add(ProductFabricLine(product_id=product.id, fabric_code="READY", stock_meters=Decimal("1000.000"), per_piece_meters=Decimal("2.000")))
        db.add(Contractor(name="Kumar Factors", contractor_type=ContractorType.stitching, is_active=True))
        po4 = PurchaseOrder(
            po_number="JUNE-004",
            product_id=product.id,
            order_quantity_pcs=4000,
            order_date=date(2026, 6, 1),
            promise_delivery_date=date(2026, 6, 30),
            status=POStatus.packing,
            design_code_snapshot="READY",
        )
        po5 = PurchaseOrder(
            po_number="JUNE-005",
            product_id=product.id,
            order_quantity_pcs=8000,
            order_date=date(2026, 6, 1),
            promise_delivery_date=date(2026, 6, 30),
            status=POStatus.cutting,
            design_code_snapshot="READY",
        )
        po10 = PurchaseOrder(
            po_number="JUNE-010",
            product_id=product.id,
            order_quantity_pcs=12000,
            order_date=date(2026, 6, 1),
            promise_delivery_date=date(2026, 6, 30),
            status=POStatus.shortage,
            design_code_snapshot="READY",
        )
        db.add_all([po4, po5, po10])
        await db.flush()
        db.add_all(
            [
                StageSummary(purchase_order_id=po4.id, stage=StageName.packing, sequence=5, input_qty=3380, completed_qty=3380, approved_qty=3380, pending_qty=0, status=StageStatus.completed),
                StageSummary(purchase_order_id=po4.id, stage=StageName.dispatch, sequence=6, input_qty=3380, pending_qty=3380, status=StageStatus.in_progress),
                StageSummary(purchase_order_id=po5.id, stage=StageName.cutting, sequence=1, input_qty=8000, pending_qty=8000, status=StageStatus.in_progress),
                StageSummary(purchase_order_id=po5.id, stage=StageName.stitching, sequence=2, input_qty=0, pending_qty=0, status=StageStatus.not_started),
                StageSummary(purchase_order_id=po10.id, stage=StageName.cutting, sequence=1, input_qty=0, pending_qty=0, status=StageStatus.not_started),
            ]
        )
        await db.commit()
        yield db
    _PENDING_WRITE.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_fabric_arrival_collects_missing_fields_then_confirms(owner_ai_db) -> None:
    first = await answer_factory_question(owner_ai_db, "Fabric for JUNE-010 has arrived")
    assert first is not None
    assert "How many meters" in first.answer

    second = await answer_factory_question(owner_ai_db, "12,000 meters from Krishna Mill")
    assert second is not None
    assert "Confirm:" in second.answer
    assert "Krishna Mill" in second.answer

    done = await answer_factory_question(owner_ai_db, "confirm")
    assert done is not None
    assert "Fabric receipt of 12000 meters" in done.answer
    receipts = list((await owner_ai_db.execute(select(FabricReceipt))).scalars().all())
    assert len(receipts) == 1

    duplicate = await answer_factory_question(owner_ai_db, "confirm")
    assert duplicate is not None
    assert "no pending update" in duplicate.answer.lower()
    receipts = list((await owner_ai_db.execute(select(FabricReceipt))).scalars().all())
    assert len(receipts) == 1


@pytest.mark.asyncio
async def test_dispatch_requires_confirmation_and_rejects_over_ready_quantity(owner_ai_db) -> None:
    preview = await answer_factory_question(owner_ai_db, "Dispatch 3000 pieces for PO JUNE-004")
    assert preview is not None
    assert "Confirm:" in preview.answer
    done = await answer_factory_question(owner_ai_db, "yes")
    assert done is not None
    assert "Dispatched 3000 pieces" in done.answer

    too_much = await answer_factory_question(owner_ai_db, "Dispatch 5000 pieces for PO JUNE-004")
    assert too_much is not None
    assert "Confirm:" in too_much.answer
    rejected = await answer_factory_question(owner_ai_db, "yes")
    assert rejected is not None
    assert "Only 380 packed pieces are available" in rejected.answer


@pytest.mark.asyncio
async def test_cutting_complete_and_delivery_date_updates_are_confirmed(owner_ai_db) -> None:
    preview = await answer_factory_question(owner_ai_db, "JUNE-005 cutting complete")
    assert preview is not None
    assert "Confirm:" in preview.answer
    done = await answer_factory_question(owner_ai_db, "haan")
    assert done is not None
    assert "Cutting for JUNE-005 is marked complete" in done.answer

    date_preview = await answer_factory_question(owner_ai_db, "Update shipment date of JUNE-005 to 30 June")
    assert date_preview is not None
    assert "Confirm:" in date_preview.answer
    date_done = await answer_factory_question(owner_ai_db, "confirm")
    assert date_done is not None
    assert "2026-06-30" in date_done.answer


@pytest.mark.asyncio
async def test_hinglish_dispatch_phrase_is_recognized(owner_ai_db) -> None:
    preview = await answer_factory_question(owner_ai_db, "JUNE-004 ka 300 piece dispatch kar do")
    assert preview is not None
    assert "Confirm:" in preview.answer
