"""Fabric meter receipts — log meters of fabric received into the warehouse (non-PO).

Each POST is atomic: the receipt row is written and `product_fabric_lines.stock_meters`
is incremented in the same DB transaction, so the running count and the audit log
can't drift apart.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_owner_or_manager
from app.models.fabric_meter_receipt import FabricMeterReceipt
from app.models.product_fabric_line import ProductFabricLine
from app.models.user import User

router = APIRouter()


class FabricMeterReceiptCreate(BaseModel):
    product_fabric_line_id: UUID
    meters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    received_at: Optional[date] = None
    mill_name: Optional[str] = Field(default=None, max_length=150)
    notes: Optional[str] = Field(default=None, max_length=2000)


class FabricMeterReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_fabric_line_id: UUID
    meters: Decimal
    received_at: date
    mill_name: Optional[str]
    notes: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime


@router.get("", response_model=List[FabricMeterReceiptRead])
async def list_receipts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
    product_fabric_line_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> List[FabricMeterReceipt]:
    stmt = (
        select(FabricMeterReceipt)
        .order_by(FabricMeterReceipt.received_at.desc(), FabricMeterReceipt.created_at.desc())
        .limit(limit)
    )
    if product_fabric_line_id is not None:
        stmt = stmt.where(FabricMeterReceipt.product_fabric_line_id == product_fabric_line_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=FabricMeterReceiptRead, status_code=201)
async def create_receipt(
    payload: FabricMeterReceiptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> FabricMeterReceipt:
    line = await db.get(ProductFabricLine, payload.product_fabric_line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Fabric line not found")

    receipt = FabricMeterReceipt(
        product_fabric_line_id=payload.product_fabric_line_id,
        meters=payload.meters,
        received_at=payload.received_at or date.today(),
        mill_name=payload.mill_name,
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(receipt)
    line.stock_meters = Decimal(line.stock_meters or 0) + payload.meters
    await db.commit()
    await db.refresh(receipt)
    return receipt
