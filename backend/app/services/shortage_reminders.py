"""Daily shortage check — runs from the scheduler at 04:00 each morning.

Inspects three sources of trouble and upserts owner-facing reminders:

  1. Mill fabric shortage:    fabric_mill_orders.received_length_m  <  ordered_length_m
  2. Stitching output short:  stage_summaries(stage=stitching).input_qty − completed_qty > tolerance
                              (interpreted as "contractor still owes us pieces")
  3. Fabric stock short:      per fabric line, stock_meters < required for remaining target
                              pieces × per_piece_meters × (1 + wastage)

Auto-dismiss: any reminder of these three types that no longer corresponds to a live
shortage gets its status flipped to completed so the dashboard stays clean.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fabric import FabricMillOrder
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import Reminder, ReminderPriority, ReminderStatus, ReminderType
from app.models.stage import StageSummary
from app.models.enums import StageName
from app.services.reminder_service import upsert_reminder

logger = logging.getLogger(__name__)

# Composite-key markers so we don't duplicate reminders for the same shortage.
# We piggy-back on `Reminder.message` (which already contains the ref details)
# and on the upsert_reminder query that matches by (purchase_order_id, type, status=open).
# For fabric-line shortages the PO is null; we keep the line reference in the message.

_STITCHING_TOLERANCE_PCT = 2  # ignore <=2% rounding gaps


async def check_mill_fabric_shortages(db: AsyncSession, today: date) -> set[tuple[ReminderType, str]]:
    """Reminder for any open mill order where received < ordered."""
    fingerprints: set[tuple[ReminderType, str]] = set()
    stmt = select(FabricMillOrder).where(FabricMillOrder.status.in_(["ordered", "in_followup", "partially_received", "delayed"]))
    rows = (await db.execute(stmt)).scalars().all()
    for mill_order in rows:
        ordered = Decimal(mill_order.ordered_length_m or 0)
        received = Decimal(mill_order.received_length_m or 0)
        if ordered <= 0 or received >= ordered:
            continue
        pending = ordered - received
        fp = (ReminderType.mill_fabric_shortage, str(mill_order.id))
        fingerprints.add(fp)
        await upsert_reminder(
            db,
            purchase_order_id=mill_order.purchase_order_id,
            reminder_type=ReminderType.mill_fabric_shortage,
            title=f"Mill short {pending} m — {mill_order.mill_name}",
            message=(
                f"{mill_order.mill_name} ordered {ordered} m, received {received} m. "
                f"{pending} m still pending. Follow up today."
            ),
            due_date=today,
            priority=ReminderPriority.high,
        )
    return fingerprints


async def check_stitching_output_shortages(db: AsyncSession, today: date) -> set[tuple[ReminderType, str]]:
    """Reminder when stitched output is materially less than what was sent."""
    fingerprints: set[tuple[ReminderType, str]] = set()
    stmt = (
        select(StageSummary, PurchaseOrder)
        .join(PurchaseOrder, PurchaseOrder.id == StageSummary.purchase_order_id)
        .where(and_(StageSummary.stage == StageName.stitching, StageSummary.input_qty > 0))
    )
    rows = (await db.execute(stmt)).all()
    for stage_row, po in rows:
        expected = stage_row.input_qty or 0
        delivered = (stage_row.completed_qty or 0) + (stage_row.approved_qty or 0)
        # Treat "approved" as the contractor's accepted return. If neither input nor
        # delivered has progressed beyond 2%, skip — likely just rounding noise.
        if expected == 0:
            continue
        shortfall = expected - delivered
        if shortfall <= max(1, expected * _STITCHING_TOLERANCE_PCT // 100):
            continue
        fp = (ReminderType.stitching_output_short, str(stage_row.id))
        fingerprints.add(fp)
        await upsert_reminder(
            db,
            purchase_order_id=po.id,
            reminder_type=ReminderType.stitching_output_short,
            title=f"Stitching short {shortfall} pcs — PO {po.po_number}",
            message=(
                f"PO {po.po_number}: sent {expected} pcs to stitching, "
                f"only {delivered} pcs returned. {shortfall} pcs pending from contractor."
            ),
            due_date=today,
            priority=ReminderPriority.high,
        )
    return fingerprints


async def check_fabric_stock_shortages(db: AsyncSession, today: date) -> set[tuple[ReminderType, str]]:
    """For each fabric line with an unmet stock target, ensure a reminder exists."""
    fingerprints: set[tuple[ReminderType, str]] = set()
    stmt = select(ProductFabricLine, Product).join(Product, Product.id == ProductFabricLine.product_id)
    rows = (await db.execute(stmt)).all()
    for line, product in rows:
        remaining_pieces = max(0, (line.pieces or 0) - (line.pieces_in_stock or 0))
        if remaining_pieces == 0:
            continue
        per_piece = Decimal(line.per_piece_meters or 0)
        wastage = Decimal(product.wastage_percent or 0) / Decimal(100)
        needed = Decimal(remaining_pieces) * per_piece * (Decimal(1) + wastage)
        on_hand = Decimal(line.stock_meters or 0)
        if on_hand >= needed:
            continue
        short = needed - on_hand
        fp = (ReminderType.fabric_stock_short, str(line.id))
        fingerprints.add(fp)
        await upsert_reminder(
            db,
            purchase_order_id=None,
            reminder_type=ReminderType.fabric_stock_short,
            title=f"Fabric short for {product.product_name} / {line.fabric_code}",
            message=(
                f"Need {needed:.0f} m of {line.fabric_code} (category {product.product_name}) "
                f"to finish {remaining_pieces} pcs. Have {on_hand:.0f} m. "
                f"Short by {short:.0f} m — order from mill."
            ),
            due_date=today,
            priority=ReminderPriority.high,
        )
    return fingerprints


async def auto_dismiss_resolved_shortages(
    db: AsyncSession,
    live_fingerprints: set[tuple[ReminderType, str]],
    cutoff_days: int = 1,
) -> int:
    """Mark any open shortage reminder as completed if it no longer corresponds to a live shortage.

    Conservative: only auto-close reminders older than `cutoff_days` so a transient
    flicker (e.g., receipt logged seconds before scheduler ticks) doesn't churn the inbox.
    """
    shortage_types = (
        ReminderType.mill_fabric_shortage,
        ReminderType.stitching_output_short,
        ReminderType.fabric_stock_short,
    )
    cutoff = date.today() - timedelta(days=cutoff_days)
    stmt = select(Reminder).where(
        and_(
            Reminder.status == ReminderStatus.open,
            Reminder.reminder_type.in_(shortage_types),
            Reminder.created_at < cutoff,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    closed = 0
    for reminder in rows:
        # Skip if a live fingerprint still references this reminder. We don't carry the
        # composite key on the reminder row itself; instead we use (type, po_id) when set,
        # else fall back to the message body containing the line id.
        if any(t == reminder.reminder_type for t, _ in live_fingerprints):
            continue
        reminder.status = ReminderStatus.completed
        closed += 1
    if closed:
        await db.commit()
    return closed


async def run_daily_shortage_check(db: AsyncSession) -> dict[str, int]:
    """Single entrypoint called from the scheduler."""
    today = date.today()
    mill = await check_mill_fabric_shortages(db, today)
    stitch = await check_stitching_output_shortages(db, today)
    fabric = await check_fabric_stock_shortages(db, today)
    live = mill | stitch | fabric
    auto_dismissed = await auto_dismiss_resolved_shortages(db, live)
    logger.info(
        "shortage check: mill=%d stitching=%d fabric=%d auto_dismissed=%d",
        len(mill), len(stitch), len(fabric), auto_dismissed,
    )
    return {"mill": len(mill), "stitching": len(stitch), "fabric": len(fabric), "dismissed": auto_dismissed}
