from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    FabricMillOrderStatus,
    FabricPlanStatus,
    FabricVerificationAction,
    FabricVerificationStatus,
    ReceiptStatus,
)


class FabricInventoryCreate(BaseModel):
    fabric_type: str = Field(min_length=1, max_length=120)
    color: str = Field(min_length=1, max_length=80)
    gsm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    width: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    available_length_m: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    approximate_rolls: Optional[int] = Field(default=None, ge=0)


class FabricReceiptCreate(FabricInventoryCreate):
    """Payload for recording approved or failed fabric receipt."""

    purchase_order_id: Optional[UUID] = None
    supplier_name: str = Field(min_length=1, max_length=150)
    status: ReceiptStatus = ReceiptStatus.approved
    quality_notes: Optional[str] = Field(default=None, max_length=500)
    received_width: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    received_gsm: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    received_rate_per_meter: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    received_meters: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    verified_by: Optional[UUID] = None
    verification_date: Optional[date] = None
    verification_status: FabricVerificationStatus = FabricVerificationStatus.pending
    mismatch_reason: Optional[str] = Field(default=None, max_length=500)
    action_taken: Optional[FabricVerificationAction] = None
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = Field(default=None, max_length=80)
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=500)
    received_at: date
    debit_amount: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class FabricInventoryRead(FabricInventoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class FabricPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    required_m: Decimal
    wastage_m: Decimal
    total_required_m: Decimal
    roll_length_m: Optional[Decimal]
    rolls_required: Optional[int]
    available_m: Decimal
    shortage_m: Decimal
    status: FabricPlanStatus
    created_at: datetime
    updated_at: datetime


class FabricReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: Optional[UUID]
    supplier_name: str
    fabric_type: str
    color: str
    gsm: Decimal
    width: Decimal
    received_length_m: Decimal
    approximate_rolls: Optional[int]
    status: ReceiptStatus
    quality_notes: Optional[str]
    received_width: Optional[Decimal]
    received_gsm: Optional[Decimal]
    received_rate_per_meter: Optional[Decimal]
    received_meters: Optional[Decimal]
    verified_by: Optional[UUID]
    verification_date: Optional[date]
    verification_status: FabricVerificationStatus
    mismatch_reason: Optional[str]
    action_taken: Optional[FabricVerificationAction]
    assigned_to: Optional[UUID]
    responsible_role: Optional[str]
    completed_by: Optional[UUID]
    completed_at: Optional[datetime]
    remarks: Optional[str]
    received_at: date
    created_at: datetime


class SupplierReturnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fabric_receipt_id: UUID
    supplier_name: str
    returned_length_m: Decimal
    reason: str
    returned_at: date
    created_at: datetime


class DebitNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fabric_receipt_id: UUID
    supplier_name: str
    amount: Optional[Decimal]
    reason: str
    note_date: date
    created_at: datetime


class FabricReceiptResult(BaseModel):
    receipt: FabricReceiptRead
    supplier_return: Optional[SupplierReturnRead] = None
    debit_note: Optional[DebitNoteRead] = None
    refreshed_plan: Optional[FabricPlanRead] = None


class FabricMillOrderCreate(BaseModel):
    purchase_order_id: UUID
    mill_name: str = Field(min_length=1, max_length=150)
    ordered_meters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    ordered_width: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    ordered_gsm: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    ordered_rate_per_meter: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    expected_quality_notes: Optional[str] = Field(default=None, max_length=500)
    committed_delivery_date: date
    actual_delivery_date: Optional[date] = None
    status: FabricMillOrderStatus = FabricMillOrderStatus.ordered
    responsible_user_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = Field(default=None, max_length=80)
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=500)


class FabricMillOrderRead(FabricMillOrderCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MillFollowUpCreate(BaseModel):
    mill_order_id: UUID
    followup_date: date
    followup_by: Optional[UUID] = None
    response_notes: Optional[str] = Field(default=None, max_length=500)
    next_followup_date: Optional[date] = None
    status: FabricMillOrderStatus = FabricMillOrderStatus.in_followup
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = Field(default=None, max_length=80)
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=500)


class MillFollowUpRead(MillFollowUpCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class FabricVerificationUpdate(BaseModel):
    receipt_id: UUID
    verification_status: FabricVerificationStatus
    action_taken: FabricVerificationAction
    verified_by: Optional[UUID] = None
    verification_date: date
    mismatch_reason: Optional[str] = Field(default=None, max_length=500)
    remarks: Optional[str] = Field(default=None, max_length=500)


class FabricIssueToCuttingCreate(BaseModel):
    purchase_order_id: UUID
    fabric_inventory_id: Optional[UUID] = None
    fabric_receipt_id: Optional[UUID] = None
    contractor_id: Optional[UUID] = None
    issued_meters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    issued_rolls: Optional[int] = Field(default=None, ge=0)
    issued_by: Optional[UUID] = None
    received_by: Optional[UUID] = None
    issue_date: date
    expected_return_date: Optional[date] = None
    status: Optional[str] = Field(default="issued", max_length=60)
    remarks: Optional[str] = Field(default=None, max_length=500)
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = Field(default=None, max_length=80)
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None


class FabricIssueToCuttingRead(FabricIssueToCuttingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class MillSplitItem(BaseModel):
    mill_name: str = Field(min_length=1, max_length=150)
    split_percent: Decimal = Field(gt=0, le=100, max_digits=6, decimal_places=3)
    committed_delivery_date: date
    ordered_width: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    ordered_gsm: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    ordered_rate_per_meter: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    responsible_user_id: Optional[UUID] = None


class MillOrderSplitCreate(BaseModel):
    purchase_order_id: UUID
    mill_order_requirement_id: Optional[UUID] = None
    splits: List[MillSplitItem]

    @model_validator(mode="after")
    def validate_total(self) -> "MillOrderSplitCreate":
        total = sum(item.split_percent for item in self.splits)
        if total != Decimal("100"):
            raise ValueError("split_percent total must be exactly 100")
        return self


class MillOrderSplitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    mill_order_requirement_id: Optional[UUID]
    mill_name: str
    split_percent: Decimal
    ordered_meters: Decimal
    committed_delivery_date: date
    status: FabricMillOrderStatus
    responsible_user_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class MillDeliveryLotCreate(BaseModel):
    fabric_mill_order_id: UUID
    lot_number: str = Field(min_length=1, max_length=80)
    delivered_meters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    received_date: date
    quality_notes: Optional[str] = Field(default=None, max_length=500)


class MillDeliveryLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fabric_mill_order_id: UUID
    lot_number: str
    delivered_meters: Decimal
    received_date: date
    quality_notes: Optional[str]
    status: FabricMillOrderStatus
    created_at: datetime


class MillOrderShiftCreate(BaseModel):
    from_mill_order_id: UUID
    to_mill_name: str = Field(min_length=1, max_length=150)
    shift_meters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    committed_delivery_date: date
    reason: Optional[str] = Field(default=None, max_length=500)
    responsible_user_id: Optional[UUID] = None
