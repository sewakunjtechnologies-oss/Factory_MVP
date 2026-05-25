from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DispatchCostType


class DispatchLoadCreate(BaseModel):
    purchase_order_id: UUID
    load_number: str = Field(min_length=1, max_length=100)
    shipped_qty: int = Field(gt=0)
    vehicle_type: Optional[str] = Field(default=None, max_length=100)
    vehicle_identifier: Optional[str] = Field(default=None, max_length=100)
    expected_piece_capacity: Optional[int] = Field(default=None, gt=0)
    actual_loaded_pieces: Optional[int] = Field(default=None, gt=0)
    cbm_capacity: Optional[Decimal] = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    cbm_used: Optional[Decimal] = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    cost_type: DispatchCostType = DispatchCostType.invoice_percent
    invoice_value: Optional[Decimal] = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    dispatch_percent: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    cbm_value: Optional[Decimal] = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    cbm_rate: Optional[Decimal] = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    manual_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    vehicle_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    shipped_at: date
    transporter_name: Optional[str] = Field(default=None, max_length=150)
    destination: Optional[str] = Field(default=None, max_length=255)
    tracking_reference: Optional[str] = Field(default=None, max_length=150)
    document_status: Optional[str] = Field(default=None, max_length=50)
    invoice_uploaded: bool = False
    packing_list_uploaded: bool = False
    eway_bill_uploaded: bool = False
    transporter_confirmation: bool = False
    buyer_dispatch_approval: bool = False
    shortfall_reason: Optional[str] = Field(default=None, max_length=255)
    linked_repair_qty: int = Field(default=0, ge=0)
    linked_alteration_qty: int = Field(default=0, ge=0)
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = Field(default=None, max_length=80)
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_cost_fields(self) -> "DispatchLoadCreate":
        if self.cost_type == DispatchCostType.invoice_percent:
            if self.invoice_value is None or self.dispatch_percent is None:
                raise ValueError("invoice_value and dispatch_percent are required for invoice_percent dispatch cost")
        elif self.cost_type == DispatchCostType.cbm:
            if self.cbm_value is None or self.cbm_rate is None:
                raise ValueError("cbm_value and cbm_rate are required for cbm dispatch cost")
        elif self.cost_type == DispatchCostType.manual and self.manual_cost is None:
            raise ValueError("manual_cost is required for manual dispatch cost")
        elif self.cost_type == DispatchCostType.vehicle_capacity:
            if self.vehicle_cost is None:
                raise ValueError("vehicle_cost is required for vehicle_capacity dispatch cost")
            if self.actual_loaded_pieces is None:
                raise ValueError("actual_loaded_pieces is required for vehicle_capacity dispatch cost")
        if self.document_status == "blocked" and self.shipped_qty > 0:
            raise ValueError("dispatch cannot proceed when document_status is blocked")
        return self


class DispatchLoadRead(DispatchLoadCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dispatch_cost: Decimal
    cost_per_piece: Decimal
    expected_cost_percent: Optional[Decimal]
    actual_cost_percent: Optional[Decimal]
    shortfall_qty: int = 0
    created_at: datetime


class DispatchSummaryRead(BaseModel):
    purchase_order_id: UUID
    total_dispatched: int
    pending_dispatch: int
    total_dispatch_cost: Decimal
    average_cost_per_piece: Decimal
    loads: List[DispatchLoadRead]


class DispatchDocumentUpdate(BaseModel):
    document_status: str = Field(min_length=1, max_length=50)
    invoice_uploaded: bool = False
    packing_list_uploaded: bool = False
    eway_bill_uploaded: bool = False
    transporter_confirmation: bool = False
    buyer_dispatch_approval: bool = False
