from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import QualityAction, StageName, StageStatus


class StageSummary(Base):
    __tablename__ = "stage_summaries"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "stage", name="uq_stage_summary_po_stage"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)
    stage: Mapped[StageName] = mapped_column(Enum(StageName, name="stage_name"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    input_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repair_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alter_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    moved_to_next_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus, name="stage_status"),
        nullable=False,
        default=StageStatus.not_started,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="stage_summaries")
    allocations: Mapped[List["ContractorAllocation"]] = relationship(
        back_populates="stage_summary",
        cascade="all, delete-orphan",
    )
    progress_entries: Mapped[List["StageProgressEntry"]] = relationship(
        back_populates="stage_summary",
        cascade="all, delete-orphan",
    )
    quality_failures: Mapped[List["QualityFailure"]] = relationship(
        back_populates="stage_summary",
        cascade="all, delete-orphan",
    )


class ContractorAllocation(Base):
    __tablename__ = "contractor_allocations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    stage_summary_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("stage_summaries.id"), nullable=False)
    stage: Mapped[StageName] = mapped_column(Enum(StageName, name="stage_name"), nullable=False)
    contractor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contractors.id"), nullable=False)
    issued_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repair_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alter_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expected_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    stage_summary: Mapped["StageSummary"] = relationship(back_populates="allocations")
    contractor: Mapped["Contractor"] = relationship(back_populates="allocations")
    progress_entries: Mapped[List["StageProgressEntry"]] = relationship(
        back_populates="allocation",
        cascade="all, delete-orphan",
    )


class StageProgressEntry(Base):
    __tablename__ = "stage_progress_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    stage_summary_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("stage_summaries.id"), nullable=False)
    allocation_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contractor_allocations.id"), nullable=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repair_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alter_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    moved_to_next_stage_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    stage_summary: Mapped["StageSummary"] = relationship(back_populates="progress_entries")
    allocation: Mapped[Optional["ContractorAllocation"]] = relationship(back_populates="progress_entries")


class QualityFailure(Base):
    __tablename__ = "quality_failures"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    stage_summary_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("stage_summaries.id"), nullable=False)
    allocation_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contractor_allocations.id"), nullable=True)
    failed_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    resolved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_resolution_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action: Mapped[QualityAction] = mapped_column(Enum(QualityAction, name="quality_action"), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_date: Mapped[date] = mapped_column(Date, nullable=False)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    stage_summary: Mapped["StageSummary"] = relationship(back_populates="quality_failures")


class CuttingAnalysis(Base):
    __tablename__ = "cutting_analysis"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    planned_cut_size: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    actual_cut_size: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    planned_consumption_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    actual_consumption_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    planned_wastage_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    actual_wastage_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    wastage_difference_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    reason_for_difference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cutting_supervisor_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MillWastageRecord(Base):
    __tablename__ = "mill_wastage_records"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    mill_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    cutting_analysis_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cutting_analysis.id"), nullable=True)
    planned_wastage_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    actual_wastage_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    wastage_difference_m: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    flag: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    recorded_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PackingOutput(Base):
    __tablename__ = "packing_outputs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    output_date: Mapped[date] = mapped_column(Date, nullable=False)
    worker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packed_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_target: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    required_workers: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    blocker_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StageCostEntry(Base):
    __tablename__ = "stage_cost_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    stage: Mapped[StageName] = mapped_column(Enum(StageName, name="stage_cost_stage_name"), nullable=False)
    contractor_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contractors.id"), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_per_piece: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    manual_cost: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_stage_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    cost_per_piece: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
