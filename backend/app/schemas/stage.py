from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import StageName, StageStatus


class StageSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    stage: StageName
    sequence: int
    input_qty: int
    completed_qty: int
    approved_qty: int
    rejected_qty: int
    repair_qty: int
    alter_qty: int
    moved_to_next_qty: int
    pending_qty: int
    status: StageStatus
    created_at: datetime
    updated_at: datetime


class ContractorAllocationCreate(BaseModel):
    stage_summary_id: UUID
    contractor_id: UUID
    issued_qty: int = Field(gt=0)
    expected_completion_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class ContractorAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stage_summary_id: UUID
    stage: StageName
    contractor_id: UUID
    issued_qty: int
    completed_qty: int
    rejected_qty: int
    repair_qty: int
    alter_qty: int
    delay_days: int
    expected_completion_date: Optional[date]
    notes: Optional[str]
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = None
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StageProgressCreate(BaseModel):
    purchase_order_id: UUID
    stage: StageName
    allocation_id: Optional[UUID] = None
    entry_date: date
    completed_today: int = Field(default=0, ge=0)
    approved_today: int = Field(default=0, ge=0)
    rejected_today: int = Field(default=0, ge=0)
    repair_today: int = Field(default=0, ge=0)
    alter_today: int = Field(default=0, ge=0)
    moved_to_next_stage_today: int = Field(default=0, ge=0)
    delay_days: int = Field(default=0, ge=0)
    remarks: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_quantities(self) -> "StageProgressCreate":
        outcome_total = self.approved_today + self.rejected_today + self.repair_today + self.alter_today
        if self.completed_today == 0 and outcome_total > 0:
            raise ValueError("completed_today is required when outcome quantities are provided")
        if self.completed_today > 0 and outcome_total != self.completed_today:
            raise ValueError("completed_today must equal approved + rejected + repair + alter")
        if self.completed_today == 0 and self.moved_to_next_stage_today == 0 and self.delay_days == 0:
            raise ValueError("progress entry must change production, movement, or delay")
        return self


class StageProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stage_summary_id: UUID
    allocation_id: Optional[UUID]
    entry_date: date
    completed_today: int
    approved_today: int
    rejected_today: int
    repair_today: int
    alter_today: int
    moved_to_next_stage_today: int
    delay_days: int
    remarks: Optional[str]
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = None
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    created_at: datetime




class CuttingAnalysisCreate(BaseModel):
    purchase_order_id: UUID
    planned_cut_size: Optional[str] = Field(default=None, max_length=120)
    actual_cut_size: Optional[str] = Field(default=None, max_length=120)
    planned_consumption_m: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    actual_consumption_m: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    planned_wastage_m: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    actual_wastage_m: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    reason_for_difference: Optional[str] = Field(default=None, max_length=500)
    cutting_supervisor_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = Field(default=None, max_length=80)
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=500)
    # Step 5: optional mill attribution so wastage feeds the per-mill history.
    mill_name: Optional[str] = Field(default=None, max_length=150)


class CuttingAnalysisRead(CuttingAnalysisCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wastage_difference_m: Decimal
    updated_at: datetime
    created_at: datetime


class MillWastageHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mill_name: str
    event_count: int
    total_planned_wastage_m: Decimal
    total_actual_wastage_m: Decimal
    total_difference_m: Decimal
    avg_difference_m: Decimal
    last_recorded_at: Optional[datetime] = None
    flag: str  # "high" | "low" | "normal" — derived from average difference


class MillWastageRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    mill_name: str
    cutting_analysis_id: Optional[UUID] = None
    planned_wastage_m: Decimal
    actual_wastage_m: Decimal
    wastage_difference_m: Decimal
    flag: str
    recorded_by: Optional[UUID] = None
    recorded_at: datetime


class PackingOutputCreate(BaseModel):
    purchase_order_id: UUID
    output_date: date
    worker_count: int = Field(ge=0)
    packed_qty: int = Field(ge=0)
    pending_qty: int = Field(ge=0)
    daily_target: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    required_workers: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    blocker_reason: Optional[str] = Field(default=None, max_length=500)
    updated_by: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = Field(default=None, max_length=80)
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = Field(default=None, max_length=500)


class PackingOutputRead(PackingOutputCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class StageCostEntryCreate(BaseModel):
    purchase_order_id: UUID
    stage: StageName
    contractor_id: Optional[UUID] = None
    qty: int = Field(default=0, ge=0)
    rate_per_piece: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    manual_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    remarks: Optional[str] = Field(default=None, max_length=500)


class StageCostEntryRead(StageCostEntryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    total_stage_cost: Decimal
    cost_per_piece: Decimal
    assigned_to: Optional[UUID] = None
    responsible_role: Optional[str] = None
    completed_by: Optional[UUID] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
