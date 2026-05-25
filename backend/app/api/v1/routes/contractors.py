from __future__ import annotations

from typing import List

from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_allocator, require_owner
from app.models.user import User
from app.schemas.contractor import ContractorCreate, ContractorRead
from app.services.stage_engine import create_contractor, list_contractors

router = APIRouter()


@router.post("", response_model=ContractorRead, status_code=201)
async def create(
    payload: ContractorCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> ContractorRead:
    return await create_contractor(db, payload)


@router.get("", response_model=List[ContractorRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_allocator)],
) -> List[ContractorRead]:
    return await list_contractors(db)
