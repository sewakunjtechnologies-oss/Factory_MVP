from __future__ import annotations

from typing import List

from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_any_allocator
from app.models.user import User
from app.schemas.stage import ContractorAllocationCreate, ContractorAllocationRead
from app.services.stage_engine import allocate_contractor, list_allocations

router = APIRouter()


@router.post("", response_model=ContractorAllocationRead, status_code=201)
async def create(
    payload: ContractorAllocationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_any_allocator)],
) -> ContractorAllocationRead:
    return await allocate_contractor(db, payload, actor_id=user.id, actor_role=user.role)


@router.get("/purchase-orders/{purchase_order_id}", response_model=List[ContractorAllocationRead])
async def list_for_po(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> List[ContractorAllocationRead]:
    return await list_allocations(db, purchase_order_id)
