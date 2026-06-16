from __future__ import annotations

from typing import List

from typing_extensions import Annotated

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner
from app.models.user import User
from app.schemas.fabric import FabricInventoryCreate, FabricInventoryRead, FabricInventoryUpdate
from app.services.fabric_planning import (
    delete_fabric_inventory,
    get_fabric_inventory,
    list_fabric_inventory,
    update_fabric_inventory,
    upsert_fabric_inventory,
)

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


@router.get("/{inventory_id}", response_model=FabricInventoryRead)
async def get_one(
    inventory_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> FabricInventoryRead:
    return await get_fabric_inventory(db, inventory_id)


@router.patch("/{inventory_id}", response_model=FabricInventoryRead)
async def update_one(
    inventory_id: UUID,
    payload: FabricInventoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> FabricInventoryRead:
    return await update_fabric_inventory(db, inventory_id, payload)


@router.delete("/{inventory_id}", status_code=204, response_class=Response)
async def delete_one(
    inventory_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> Response:
    await delete_fabric_inventory(db, inventory_id)
    return Response(status_code=204)
