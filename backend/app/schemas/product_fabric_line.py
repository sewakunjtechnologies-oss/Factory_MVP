from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


StageStatus = Literal["pending", "in_progress", "done"]
StockStatus = Literal["extra", "in_stock", "ok", "nil", "short", "unknown"]


class ProductFabricLineBase(BaseModel):
    fabric_code: str = Field(min_length=1, max_length=80)
    pieces: int = Field(ge=0)
    pieces_in_stock: int = Field(default=0, ge=0)
    pieces_short: int = Field(default=0, ge=0)
    stock_status: StockStatus = "unknown"
    per_piece_meters: Decimal = Field(ge=0, max_digits=8, decimal_places=3)
    stock_meters: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    pieces_per_bale: int = Field(default=0, ge=0)
    bale_size_cbm: Decimal = Field(default=Decimal("0"), ge=0, max_digits=8, decimal_places=4)
    bale_weight_kg: Decimal = Field(default=Decimal("0"), ge=0, max_digits=8, decimal_places=2)
    cutting: StageStatus = "pending"
    stitching: StageStatus = "pending"
    packing: StageStatus = "pending"
    dispatch: StageStatus = "pending"
    notes: Optional[str] = Field(default=None, max_length=2000)


class ProductFabricLineCreate(ProductFabricLineBase):
    product_id: UUID


class ProductFabricLineUpdate(BaseModel):
    pieces: Optional[int] = Field(default=None, ge=0)
    pieces_in_stock: Optional[int] = Field(default=None, ge=0)
    pieces_short: Optional[int] = Field(default=None, ge=0)
    stock_status: Optional[StockStatus] = None
    per_piece_meters: Optional[Decimal] = Field(default=None, ge=0, max_digits=8, decimal_places=3)
    stock_meters: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    pieces_per_bale: Optional[int] = Field(default=None, ge=0)
    bale_size_cbm: Optional[Decimal] = Field(default=None, ge=0, max_digits=8, decimal_places=4)
    bale_weight_kg: Optional[Decimal] = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    cutting: Optional[StageStatus] = None
    stitching: Optional[StageStatus] = None
    packing: Optional[StageStatus] = None
    dispatch: Optional[StageStatus] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class ProductFabricLineRead(ProductFabricLineBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    created_at: datetime
    updated_at: datetime
