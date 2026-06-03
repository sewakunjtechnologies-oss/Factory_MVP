from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import POStatus
from app.models.enums import PODesignStatus
from app.schemas.fabric_design import PurchaseOrderDesignInput
from app.schemas.fabric import FabricPlanRead
from app.schemas.product import ProductRead
from app.schemas.stage import StageSummaryRead


class PurchaseOrderCreate(PurchaseOrderDesignInput):
    po_number: str = Field(min_length=1, max_length=100)
    product_id: UUID
    order_quantity_pcs: int = Field(gt=0)
    mrp: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    selling_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    order_date: date
    promise_delivery_date: date
    notes: Optional[str] = Field(default=None, max_length=500)
    priority_level: Optional[str] = Field(default="normal", max_length=30)
    priority_reason: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_delivery_date(self) -> "PurchaseOrderCreate":
        if self.promise_delivery_date < self.order_date:
            raise ValueError("promise_delivery_date cannot be earlier than order_date")
        return self


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_number: str
    product_id: UUID
    order_quantity_pcs: int
    mrp: Optional[Decimal]
    selling_price: Optional[Decimal]
    order_date: date
    promise_delivery_date: date
    actual_delivery_date: Optional[date]
    status: POStatus
    notes: Optional[str]
    fabric_design_id: Optional[UUID]
    design_name_snapshot: Optional[str]
    design_code_snapshot: Optional[str]
    design_image_url_snapshot: Optional[str]
    design_status: PODesignStatus
    priority_level: Optional[str]
    priority_reason: Optional[str]
    priority_updated_by: Optional[UUID]
    priority_updated_at: Optional[datetime]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    product: Optional[ProductRead] = None
    fabric_plan: Optional[FabricPlanRead] = None
    stage_summaries: List[StageSummaryRead] = Field(default_factory=list)
    # Stock lookup populated by the service layer — joins this PO's
    # (product_id, design_code_snapshot) to product_fabric_lines so the owner
    # sees "you have N pieces of this fabric in stock; only M need to be made".
    pieces_in_stock_for_fabric: int = 0
    pieces_to_make: int = 0  # max(0, order_quantity_pcs - pieces_in_stock_for_fabric)


class PurchaseOrderUpdate(BaseModel):
    """Partial update — only the fields the owner explicitly changes are sent."""

    po_number: Optional[str] = Field(default=None, min_length=1, max_length=100)
    product_id: Optional[UUID] = None
    order_quantity_pcs: Optional[int] = Field(default=None, gt=0)
    mrp: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    selling_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    order_date: Optional[date] = None
    promise_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    status: Optional[POStatus] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    design_name_snapshot: Optional[str] = Field(default=None, max_length=180)
    design_code_snapshot: Optional[str] = Field(default=None, max_length=30)
    priority_level: Optional[str] = Field(default=None, max_length=30)
    priority_reason: Optional[str] = Field(default=None, max_length=500)


class PurchaseOrderPriorityUpdate(BaseModel):
    priority_level: str = Field(min_length=1, max_length=30)
    priority_reason: Optional[str] = Field(default=None, max_length=500)
