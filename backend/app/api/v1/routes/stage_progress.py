from __future__ import annotations

from typing import Dict, List

from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.user import User
from app.schemas.stage import StageCostEntryCreate, StageCostEntryRead, StageProgressCreate, StageProgressRead, StageSummaryRead
from app.services.stage_engine import (
    create_stage_cost_entry,
    get_stage_wise_cost_summary,
    list_stage_cost_entries,
    list_stage_progress_entries,
    list_stage_summaries,
    record_stage_progress,
)

router = APIRouter()


@router.post("", response_model=StageProgressRead, status_code=201)
async def create(
    payload: StageProgressCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> StageProgressRead:
    return await record_stage_progress(db, payload, actor_id=user.id, actor_role=user.role)


@router.get("/purchase-orders/{purchase_order_id}/summaries", response_model=List[StageSummaryRead])
async def summaries(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[StageSummaryRead]:
    return await list_stage_summaries(db, purchase_order_id)


@router.get("/purchase-orders/{purchase_order_id}/entries", response_model=List[StageProgressRead])
async def entries(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[StageProgressRead]:
    return await list_stage_progress_entries(db, purchase_order_id)


@router.post("/stage-costs", response_model=StageCostEntryRead, status_code=201)
async def create_cost_entry(
    payload: StageCostEntryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> StageCostEntryRead:
    return await create_stage_cost_entry(db, payload)


@router.get("/stage-costs/purchase-orders/{purchase_order_id}", response_model=List[StageCostEntryRead])
async def list_cost_entries(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[StageCostEntryRead]:
    return await list_stage_cost_entries(db, purchase_order_id)


@router.get("/stage-costs/purchase-orders/{purchase_order_id}/summary")
async def stage_cost_summary(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> Dict[str, object]:
    return await get_stage_wise_cost_summary(db, purchase_order_id)
