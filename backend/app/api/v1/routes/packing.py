from __future__ import annotations

from typing import List
from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_owner, require_owner_or_manager, require_packer
from app.models.user import User
from app.schemas.dashboard import PackingAnalysisRead
from app.schemas.stage import PackingOutputCreate, PackingOutputRead
from app.services.packing_engine import analyze_packing
from app.services.packing_planner import PackingPlanRequest, PackingPlanResponse, plan as plan_packing
from app.services.stage_engine import list_packing_outputs, update_packing_output

router = APIRouter()


@router.get("/purchase-orders/{purchase_order_id}/analysis", response_model=PackingAnalysisRead)
async def analysis(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
    avg_per_packer: int = Query(gt=0),
    actual_packers: int = Query(default=0, ge=0),
) -> PackingAnalysisRead:
    return await analyze_packing(db, purchase_order_id, avg_per_packer, actual_packers)


@router.post("/output", response_model=PackingOutputRead, status_code=201)
async def update_output(
    payload: PackingOutputCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_packer)],
) -> PackingOutputRead:
    if payload.updated_by is None:
        payload.updated_by = user.id
    return await update_packing_output(db, payload)


@router.get("/output/purchase-orders/{purchase_order_id}", response_model=List[PackingOutputRead])
async def list_output(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[PackingOutputRead]:
    return await list_packing_outputs(db, purchase_order_id)


@router.post("/plan", response_model=PackingPlanResponse)
async def plan(
    payload: PackingPlanRequest,
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> PackingPlanResponse:
    """Pure calculator: total_pieces + packers + target_days OR per_packer_per_day."""
    return plan_packing(payload)
