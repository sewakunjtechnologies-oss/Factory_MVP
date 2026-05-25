from __future__ import annotations

from decimal import Decimal
from typing import List

from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_dispatch_document_user, require_dispatcher, require_owner_or_manager
from app.models.user import User
from app.schemas.dispatch import DispatchDocumentUpdate, DispatchLoadCreate, DispatchLoadRead, DispatchSummaryRead
from app.services.dispatch_engine import create_dispatch_load, get_dispatch_summary, list_dispatch_loads, update_dispatch_documents
from app.services.dispatch_planner import plan_dispatch

router = APIRouter()


class DispatchPlanRequest(BaseModel):
    vehicle_id: UUID = Field(description="Pick which truck to fill from /api/v1/vehicles.")
    category_priority: List[str] = Field(
        min_length=1,
        description="Category names in priority order. Truck fills the first category, then spills into the next, etc.",
    )


class DispatchPlanItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_fabric_line_id: UUID
    category: str
    fabric_code: str
    bales: int
    pieces: int
    cbm: Decimal
    weight_kg: Decimal


class DispatchPlanLeftover(BaseModel):
    category: str
    fabric_code: str
    reason: str
    available_pieces: int


class DispatchPlanResponse(BaseModel):
    vehicle_id: UUID
    vehicle_name: str
    cbm_capacity: Decimal
    max_weight_kg: Decimal
    used_cbm: Decimal
    used_weight_kg: Decimal
    fill_pct_cbm: float
    fill_pct_weight: float
    total_bales: int
    total_pieces: int
    items: List[DispatchPlanItem]
    leftover: List[DispatchPlanLeftover]


@router.post("/plan", response_model=DispatchPlanResponse)
async def make_dispatch_plan(
    payload: DispatchPlanRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> DispatchPlanResponse:
    plan = await plan_dispatch(
        db,
        vehicle_id=payload.vehicle_id,
        category_priority=payload.category_priority,
    )
    return DispatchPlanResponse(
        vehicle_id=plan.vehicle_id,
        vehicle_name=plan.vehicle_name,
        cbm_capacity=plan.cbm_capacity,
        max_weight_kg=plan.max_weight_kg,
        used_cbm=plan.used_cbm,
        used_weight_kg=plan.used_weight_kg,
        fill_pct_cbm=plan.fill_pct_cbm,
        fill_pct_weight=plan.fill_pct_weight,
        total_bales=plan.total_bales,
        total_pieces=plan.total_pieces,
        items=[DispatchPlanItem.model_validate(i) for i in plan.items],
        leftover=[DispatchPlanLeftover(**lv) for lv in plan.leftover],
    )


@router.post("", response_model=DispatchLoadRead, status_code=201)
async def create(
    payload: DispatchLoadCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_dispatcher)],
) -> DispatchLoadRead:
    return await create_dispatch_load(db, payload)


@router.get("/purchase-orders/{purchase_order_id}", response_model=List[DispatchLoadRead])
async def list_for_po(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_dispatcher)],
) -> List[DispatchLoadRead]:
    return await list_dispatch_loads(db, purchase_order_id)


@router.get("/purchase-orders/{purchase_order_id}/summary", response_model=DispatchSummaryRead)
async def summary_for_po(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_dispatcher)],
) -> DispatchSummaryRead:
    return await get_dispatch_summary(db, purchase_order_id)


@router.post("/{dispatch_load_id}/documents", response_model=DispatchLoadRead)
async def update_documents(
    dispatch_load_id: UUID,
    payload: DispatchDocumentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_dispatch_document_user)],
) -> DispatchLoadRead:
    return await update_dispatch_documents(
        db,
        dispatch_load_id=dispatch_load_id,
        document_status=payload.document_status,
        invoice_uploaded=payload.invoice_uploaded,
        packing_list_uploaded=payload.packing_list_uploaded,
        eway_bill_uploaded=payload.eway_bill_uploaded,
        transporter_confirmation=payload.transporter_confirmation,
        buyer_dispatch_approval=payload.buyer_dispatch_approval,
        updated_by=user.id,
        updated_role=user.role.value,
    )
