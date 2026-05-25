from __future__ import annotations

from datetime import date
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StageName
from app.schemas.dashboard import PackingAnalysisRead
from app.services.purchase_order_service import get_purchase_order


async def analyze_packing(
    db: AsyncSession,
    purchase_order_id: UUID,
    avg_per_packer: int,
    actual_packers: int = 0,
    as_of: date | None = None,
) -> PackingAnalysisRead:
    if avg_per_packer <= 0:
        avg_per_packer = 1
    if actual_packers < 0:
        actual_packers = 0
    today = as_of or date.today()
    po = await get_purchase_order(db, purchase_order_id)
    packing_stage = next(stage for stage in po.stage_summaries if stage.stage == StageName.packing)
    remaining_qty = max(po.order_quantity_pcs - packing_stage.approved_qty, 0)
    raw_days_left = (po.promise_delivery_date - today).days
    days_left = max(raw_days_left, 1)
    daily_target = remaining_qty / days_left
    required_packers = remaining_qty / (days_left * avg_per_packer)
    rounded_required = ceil(required_packers * 100) / 100
    # Owner's mental model: how many pieces must EACH packer pack per day
    # given the packers actually assigned.
    if actual_packers > 0:
        pieces_per_packer_per_day = ceil((daily_target / actual_packers) * 100) / 100
    else:
        pieces_per_packer_per_day = 0.0
    return PackingAnalysisRead(
        purchase_order_id=po.id,
        remaining_qty=remaining_qty,
        days_left=days_left,
        avg_per_packer=avg_per_packer,
        actual_packers=actual_packers,
        daily_target=ceil(daily_target * 100) / 100,
        required_packers=rounded_required,
        pieces_per_packer_per_day=pieces_per_packer_per_day,
        packing_risk=rounded_required > actual_packers,
    )
