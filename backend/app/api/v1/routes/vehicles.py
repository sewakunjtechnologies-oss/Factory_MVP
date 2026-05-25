"""Vehicles master — CBM + weight capacity per truck. Used by the dispatch
load planner to decide which fabric bales fit on a given truck."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_owner, require_owner_or_manager
from app.models.user import User
from app.models.vehicle import Vehicle

router = APIRouter()


class VehicleBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    registration_number: Optional[str] = Field(default=None, max_length=40)
    cbm_capacity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    max_weight_kg: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    registration_number: Optional[str] = Field(default=None, max_length=40)
    cbm_capacity: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    max_weight_kg: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


class VehicleRead(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[VehicleRead])
async def list_vehicles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
    include_inactive: bool = False,
) -> List[Vehicle]:
    stmt = select(Vehicle).order_by(Vehicle.cbm_capacity.asc())
    if not include_inactive:
        stmt = stmt.where(Vehicle.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=VehicleRead, status_code=201)
async def create_vehicle(
    payload: VehicleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> Vehicle:
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> Vehicle:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, k, v)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=204, response_class=Response)
async def delete_vehicle(
    vehicle_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> Response:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    # Soft-delete by deactivating — historical dispatch loads keep referring to it.
    vehicle.is_active = False
    await db.commit()
    return Response(status_code=204)
