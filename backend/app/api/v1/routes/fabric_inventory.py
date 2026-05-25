from __future__ import annotations

from typing import List

from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner
from app.models.user import User
from app.schemas.fabric import FabricInventoryCreate, FabricInventoryRead
from app.services.fabric_planning import list_fabric_inventory, upsert_fabric_inventory

router = APIRouter()


@router.post("", response_model=FabricInventoryRead, status_code=201)
async def upsert(
    payload: FabricInventoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> FabricInventoryRead:
    return await upsert_fabric_inventory(db, payload)


@router.get("", response_model=List[FabricInventoryRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[FabricInventoryRead]:
    return await list_fabric_inventory(db)
