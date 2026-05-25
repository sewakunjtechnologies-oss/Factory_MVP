from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    FabricMillOrderStatus,
    FabricPlanStatus,
    FabricVerificationAction,
    FabricVerificationStatus,
    ReceiptStatus,
)


class FabricInventory(Base):
    __tablename__ = "fabric_inventory"
    __table_args__ = (
        UniqueConstraint("fabric_type", "color", "gsm", "width", name="uq_fabric_inventory_spec"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    fabric_type: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(80), nullable=False)
    gsm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    width: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    available_length_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    approximate_rolls: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class FabricPlan(Base):
    __tablename__ = "fabric_plans"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("purchase_orders.id"),
        unique=True,
        nullable=False,
    )
    required_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    wastage_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    total_required_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    roll_length_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    rolls_required: Mapped[Optional[int]] = mapped_column(nullable=True)
    available_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    shortage_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[FabricPlanStatus] = mapped_column(
        Enum(FabricPlanStatus, name="fabric_plan_status"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="fabric_plan")


class FabricReceipt(Base):
    __tablename__ = "fabric_receipts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=True)
    supplier_name: Mapped[str] = mapped_column(String(150), nullable=False)
    fabric_type: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(80), nullable=False)
    gsm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    width: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    received_length_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    approximate_rolls: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[ReceiptStatus] = mapped_column(Enum(ReceiptStatus, name="receipt_status"), nullable=False)
    quality_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    received_gsm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    received_rate_per_meter: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    received_meters: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)
    verified_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verification_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    verification_status: Mapped[FabricVerificationStatus] = mapped_column(
        Enum(FabricVerificationStatus, name="fabric_verification_status"),
        nullable=False,
        default=FabricVerificationStatus.pending,
    )
    mismatch_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_taken: Mapped[Optional[FabricVerificationAction]] = mapped_column(
        Enum(FabricVerificationAction, name="fabric_verification_action"),
        nullable=True,
    )
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupplierReturn(Base):
    __tablename__ = "supplier_returns"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    fabric_receipt_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_receipts.id"), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(150), nullable=False)
    returned_length_m: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    returned_at: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DebitNote(Base):
    __tablename__ = "debit_notes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    fabric_receipt_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_receipts.id"), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(150), nullable=False)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    note_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FabricMillOrder(Base):
    __tablename__ = "fabric_mill_orders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    mill_name: Mapped[str] = mapped_column(String(150), nullable=False)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, unique=True)
    ordered_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    ordered_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    ordered_gsm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    ordered_rate_per_meter: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    expected_quality_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    committed_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[FabricMillOrderStatus] = mapped_column(
        Enum(FabricMillOrderStatus, name="fabric_mill_order_status"),
        nullable=False,
        default=FabricMillOrderStatus.ordered,
    )
    responsible_user_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MillFollowUp(Base):
    __tablename__ = "mill_followups"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    mill_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_mill_orders.id"), nullable=False, index=True)
    followup_date: Mapped[date] = mapped_column(Date, nullable=False)
    followup_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    response_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_followup_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[FabricMillOrderStatus] = mapped_column(
        Enum(FabricMillOrderStatus, name="mill_followup_status"),
        nullable=False,
        default=FabricMillOrderStatus.in_followup,
    )
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FabricIssueToCutting(Base):
    __tablename__ = "fabric_issue_to_cutting"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    fabric_inventory_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_inventory.id"), nullable=True)
    fabric_receipt_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_receipts.id"), nullable=True)
    contractor_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contractors.id"), nullable=True)
    issued_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    issued_rolls: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    issued_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    received_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, default="issued")
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MillOrderSplit(Base):
    __tablename__ = "mill_order_splits"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    mill_order_requirement_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("mill_order_requirements.id"), nullable=True, index=True)
    mill_name: Mapped[str] = mapped_column(String(150), nullable=False)
    split_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    ordered_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    committed_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FabricMillOrderStatus] = mapped_column(
        Enum(FabricMillOrderStatus, name="mill_order_split_status"),
        nullable=False,
        default=FabricMillOrderStatus.ordered,
    )
    responsible_user_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MillDeliveryLot(Base):
    __tablename__ = "mill_delivery_lots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    fabric_mill_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_mill_orders.id"), nullable=False, index=True)
    lot_number: Mapped[str] = mapped_column(String(80), nullable=False)
    delivered_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    quality_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[FabricMillOrderStatus] = mapped_column(
        Enum(FabricMillOrderStatus, name="mill_delivery_lot_status"),
        nullable=False,
        default=FabricMillOrderStatus.partially_received,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MillOrderStatusHistory(Base):
    __tablename__ = "mill_order_status_history"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    fabric_mill_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_mill_orders.id"), nullable=False, index=True)
    previous_status: Mapped[Optional[FabricMillOrderStatus]] = mapped_column(
        Enum(FabricMillOrderStatus, name="mill_order_prev_status"),
        nullable=True,
    )
    new_status: Mapped[FabricMillOrderStatus] = mapped_column(
        Enum(FabricMillOrderStatus, name="mill_order_new_status"),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
