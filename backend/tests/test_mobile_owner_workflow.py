from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.alert import Alert
from app.models.enums import POStatus
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import Reminder, ReminderPriority, ReminderStatus, ReminderType
from app.schemas.mobile import MobilePOCreate
from app.services.exceptions import DomainError
from app.services.mobile_workflow import create_mobile_po, get_transition_preview, mark_mobile_reminder_handled, snooze_mobile_reminder


@pytest_asyncio.fixture
async def mobile_db(tmp_path):
    from app import models  # noqa: F401

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'mobile_owner.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        product = Product(
            product_name="109-GARDEN-BLOOM",
            product_category="category",
            size="140x215",
            design="Garden Bloom",
            color="Multi",
            fabric_type="Cotton",
            gsm=Decimal("109"),
            width=Decimal("140"),
            per_piece_fabric_usage_m=Decimal("2.000"),
            wastage_percent=Decimal("0"),
        )
        db.add(product)
        await db.flush()
        line = ProductFabricLine(
            product_id=product.id,
            fabric_code="109-GARDEN-BLOOM-140X215-PL-TIR-10-26",
            per_piece_meters=Decimal("2.000"),
            stock_meters=Decimal("100.000"),
            pieces_in_stock=0,
        )
        db.add(line)
        await db.commit()
        yield db, line
    await engine.dispose()


@pytest.mark.asyncio
async def test_mobile_po_creation_with_month_runs_fabric_check_ready(mobile_db) -> None:
    db, line = mobile_db
    card = await create_mobile_po(db, MobilePOCreate(category_option_id=line.id, quantity=50, delivery_mode="month", delivery_month="2026-07"), None)
    assert card.po_number.startswith("MOB-20260731")
    assert card.current_stage == "FABRIC_READY"
    assert card.required_fabric_m == Decimal("100.000")
    assert card.shortage_m == Decimal("0.000")


@pytest.mark.asyncio
async def test_mobile_po_creation_with_exact_date_creates_shortage_and_reminder(mobile_db) -> None:
    db, line = mobile_db
    card = await create_mobile_po(db, MobilePOCreate(category_option_id=line.id, quantity=80, delivery_mode="date", delivery_date=date(2026, 7, 15)), None)
    assert card.current_stage == "FABRIC_SHORTAGE"
    assert card.shortage_m == Decimal("60.000")
    reminders = list((await db.execute(select(Reminder))).scalars().all())
    assert reminders
    assert reminders[0].reminder_type == ReminderType.fabric_order_pending


@pytest.mark.asyncio
async def test_mobile_shortage_transition_requires_mill_order_details(mobile_db) -> None:
    db, line = mobile_db
    card = await create_mobile_po(db, MobilePOCreate(category_option_id=line.id, quantity=80, delivery_mode="date", delivery_date=date(2026, 7, 15)), None)
    preview = await get_transition_preview(db, card.id)
    assert preview.action_label == "Prepare Mill Order"
    assert {field["name"] for field in preview.required_fields} >= {"mill_name", "meters", "expected_delivery_date"}


@pytest.mark.asyncio
async def test_mobile_reminder_snooze_and_handled(mobile_db) -> None:
    db, _line = mobile_db
    po = PurchaseOrder(
        po_number="REM-001",
        product_id=(await db.execute(select(Product.id))).scalar_one(),
        order_quantity_pcs=1,
        order_date=date.today(),
        promise_delivery_date=date.today(),
        status=POStatus.shortage,
    )
    db.add(po)
    await db.flush()
    reminder = Reminder(
        purchase_order_id=po.id,
        reminder_type=ReminderType.fabric_order_pending,
        title="Fabric pending",
        message="Order fabric",
        due_date=date.today(),
        priority=ReminderPriority.high,
        status=ReminderStatus.open,
    )
    db.add(reminder)
    await db.commit()

    await snooze_mobile_reminder(db, reminder.id, hours=4, until_date=date(2026, 7, 20), actor_id=None)
    refreshed = await db.get(Reminder, reminder.id)
    assert refreshed is not None
    assert refreshed.due_date == date(2026, 7, 20)

    await mark_mobile_reminder_handled(db, reminder.id, actor_id=None)
    refreshed = await db.get(Reminder, reminder.id)
    assert refreshed is not None
    assert refreshed.status == ReminderStatus.completed


def test_historical_import_preview_counts() -> None:
    from seed.import_owner_may_june_historical_pos import JUNE_BATCH, MAY_BATCH, build_rows

    rows = build_rows()
    may = [row for row in rows if row.batch == MAY_BATCH]
    june = [row for row in rows if row.batch == JUNE_BATCH]
    assert len(may) == 19
    assert len(june) == 37
    assert sum(row.quantity for row in may) == 84632
    assert sum(row.quantity for row in june) == 200902
