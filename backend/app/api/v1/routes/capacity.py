from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_owner
from app.models.enums import CapacityStage, StageName
from app.models.purchase_order import PurchaseOrder
from app.models.stage import StageSummary
from app.models.user import User
from app.services.exceptions import DomainError

router = APIRouter()

DEFAULT_DAILY_CAPACITY = {
    CapacityStage.cutting: 5000,
    CapacityStage.stitching: 3500,
    CapacityStage.packing: 6000,
}


class CapacityProfileCreate(BaseModel):
    product_type: str = Field(default="other", max_length=80)
    stage: CapacityStage
    daily_capacity_qty: int = Field(gt=0)
    worker_count: int = Field(ge=0)
    overtime_allowed: bool = False
    include_sunday: bool = False
    effective_from: date
    is_active: bool = True


class CapacityProfileRead(CapacityProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class CapacityForecastRead(BaseModel):
    purchase_order_id: UUID
    po_number: str
    product_type: str
    order_quantity_pcs: int
    stage: CapacityStage
    daily_capacity_qty: int
    worker_count: int
    days_required: int
    forecast_completion_date: date
    promise_delivery_date: date
    shipment_risk: bool


class UnderutilizationRead(BaseModel):
    stage: CapacityStage
    idle_date: date
    available_capacity_qty: int
    risk_type: str
    message: str


def _default_profiles() -> list[CapacityProfileRead]:
    now = datetime.utcnow()
    return [
        CapacityProfileRead(
            id=uuid4(),
            product_type="other",
            stage=stage,
            daily_capacity_qty=capacity,
            worker_count=0,
            overtime_allowed=False,
            include_sunday=False,
            effective_from=date.today(),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        for stage, capacity in DEFAULT_DAILY_CAPACITY.items()
    ]


def _stage_name(stage: CapacityStage) -> StageName:
    if stage == CapacityStage.cutting:
        return StageName.cutting
    if stage == CapacityStage.stitching:
        return StageName.stitching
    return StageName.packing


def _product_type(po: PurchaseOrder) -> str:
    name = (po.product.product_name if po.product else "").lower()
    if "pillow" in name:
        return "pillow"
    if "fitted" in name:
        return "fitted_sheet"
    if "king" in name:
        return "king_bedsheet"
    if "double" in name:
        return "double_bedsheet"
    if "single" in name:
        return "single_bedsheet"
    return "other"


@router.get("/profiles", response_model=list[CapacityProfileRead])
async def list_profiles(
    _: Annotated[User, Depends(require_owner)],
    active_only: bool = True,
) -> list[CapacityProfileRead]:
    return _default_profiles()


@router.post("/profiles", response_model=CapacityProfileRead, status_code=201)
async def create_profile(
    payload: CapacityProfileCreate,
    _: Annotated[User, Depends(require_owner)],
) -> CapacityProfileRead:
    now = datetime.utcnow()
    return CapacityProfileRead(**payload.model_dump(), id=uuid4(), created_at=now, updated_at=now)


@router.get("/forecast/{purchase_order_id}", response_model=CapacityForecastRead)
async def forecast(
    purchase_order_id: UUID,
    stage: CapacityStage,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> CapacityForecastRead:
    result = await db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == purchase_order_id)
        .options(selectinload(PurchaseOrder.product))
    )
    po = result.scalar_one_or_none()
    if po is None:
        raise DomainError(status_code=404, detail="Purchase order not found")

    stage_result = await db.execute(
        select(StageSummary).where(
            StageSummary.purchase_order_id == purchase_order_id,
            StageSummary.stage == _stage_name(stage),
        )
    )
    stage_summary = stage_result.scalar_one_or_none()
    pending_qty = stage_summary.pending_qty if stage_summary is not None and stage_summary.input_qty > 0 else po.order_quantity_pcs
    daily_capacity = DEFAULT_DAILY_CAPACITY[stage]
    days_required = max(1, ceil(max(pending_qty, 0) / daily_capacity)) if pending_qty > 0 else 0
    forecast_completion = date.today() + timedelta(days=days_required)

    return CapacityForecastRead(
        purchase_order_id=po.id,
        po_number=po.po_number,
        product_type=_product_type(po),
        order_quantity_pcs=po.order_quantity_pcs,
        stage=stage,
        daily_capacity_qty=daily_capacity,
        worker_count=0,
        days_required=days_required,
        forecast_completion_date=forecast_completion,
        promise_delivery_date=po.promise_delivery_date,
        shipment_risk=forecast_completion > po.promise_delivery_date,
    )


@router.get("/underutilization", response_model=UnderutilizationRead)
async def underutilization(
    stage: CapacityStage,
    _: Annotated[User, Depends(require_owner)],
) -> UnderutilizationRead:
    capacity = DEFAULT_DAILY_CAPACITY[stage]
    return UnderutilizationRead(
        stage=stage,
        idle_date=date.today(),
        available_capacity_qty=capacity,
        risk_type="not_tracked",
        message="Capacity utilization tracking is not configured yet; using demo daily capacity.",
    )
