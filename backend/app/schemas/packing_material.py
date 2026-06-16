from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


PackingMaterialStatus = Literal["in_stock", "ordered", "received", "shortage", "consumed", "unknown"]


class PackingMaterialBase(BaseModel):
    purchase_order_id: Optional[UUID] = None
    po_number: Optional[str] = Field(default=None, max_length=100)
    category_name: str = Field(min_length=1, max_length=180)
    material_name: str = Field(min_length=1, max_length=120)
    material_type: str = Field(default="other", min_length=1, max_length=60)
    unit: str = Field(default="pcs", min_length=1, max_length=30)
    required_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    in_stock_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    ordered_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    received_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    consumed_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    printed_consumption_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    actual_consumption_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    printed_stock_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    actual_stock_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    shortage_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    status: PackingMaterialStatus = "unknown"
    supplier_name: Optional[str] = Field(default=None, max_length=150)
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class PackingMaterialCreate(PackingMaterialBase):
    pass


class PackingMaterialUpdate(BaseModel):
    purchase_order_id: Optional[UUID] = None
    po_number: Optional[str] = Field(default=None, max_length=100)
    category_name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    material_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    material_type: Optional[str] = Field(default=None, min_length=1, max_length=60)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=30)
    required_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    in_stock_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    ordered_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    received_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    consumed_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    printed_consumption_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    actual_consumption_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    printed_stock_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    actual_stock_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    shortage_qty: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    status: Optional[PackingMaterialStatus] = None
    supplier_name: Optional[str] = Field(default=None, max_length=150)
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class PackingMaterialRead(PackingMaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class PackingMaterialBackfillSummary(BaseModel):
    rows_created: int
    rows_updated: int
    purchase_orders_scanned: int


class PackingMaterialCategoryDemand(BaseModel):
    category: str
    order_count: int
    total_pieces: int
    material_rule: str
