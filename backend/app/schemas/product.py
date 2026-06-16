from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    product_name: str = Field(min_length=1, max_length=150)
    product_category: str = Field(default="bedsheet", min_length=1, max_length=100)
    size: str = Field(min_length=1, max_length=100)
    design: str = Field(min_length=1, max_length=120)
    # Color is detected from the product photo by the AI vision system; clients no longer enter it.
    color: Optional[str] = Field(default=None, max_length=80)
    fabric_type: str = Field(min_length=1, max_length=120)
    gsm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    # Width is inferred from `size` server-side; clients no longer enter it.
    width: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    per_piece_fabric_usage_m: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    wastage_percent: Decimal = Field(default=0, ge=0, le=100, max_digits=5, decimal_places=2)
    roll_length_m: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    product_photo_url: Optional[str] = Field(default=None, max_length=500)


class ProductCreate(ProductBase):
    """Payload for creating a single-product factory item."""


class ProductUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    product_category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    size: Optional[str] = Field(default=None, min_length=1, max_length=100)
    design: Optional[str] = Field(default=None, min_length=1, max_length=120)
    color: Optional[str] = Field(default=None, max_length=80)
    fabric_type: Optional[str] = Field(default=None, min_length=1, max_length=120)
    gsm: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    width: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    per_piece_fabric_usage_m: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    wastage_percent: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    roll_length_m: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    product_photo_url: Optional[str] = Field(default=None, max_length=500)


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
