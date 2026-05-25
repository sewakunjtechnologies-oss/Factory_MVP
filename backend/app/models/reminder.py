from __future__ import annotations

from enum import Enum
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID

from app.core.database import Base


class ReminderPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ReminderStatus(str, Enum):
    open = "open"
    completed = "completed"
    cancelled = "cancelled"


class ReminderType(str, Enum):
    fabric_not_ordered = "fabric_not_ordered"
    fabric_order_pending = "fabric_order_pending"
    mill_delivery_due = "mill_delivery_due"
    mill_delivery_due_today = "mill_delivery_due_today"
    mill_delivery_due_tomorrow = "mill_delivery_due_tomorrow"
    mill_delivery_overdue = "mill_delivery_overdue"
    fabric_verification_pending = "fabric_verification_pending"
    cutting_due = "cutting_due"
    stitching_due = "stitching_due"
    qc_pending = "qc_pending"
    packing_due = "packing_due"
    dispatch_due = "dispatch_due"
    followup_due = "followup_due"
    partial_delivery_pending = "partial_delivery_pending"
    replacement_fabric_pending = "replacement_fabric_pending"
    mill_fabric_shortage = "mill_fabric_shortage"
    stitching_output_short = "stitching_output_short"
    fabric_stock_short = "fabric_stock_short"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("purchase_orders.id"), nullable=True)
    reminder_type: Mapped[ReminderType] = mapped_column(SAEnum(ReminderType, name="reminder_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    priority: Mapped[ReminderPriority] = mapped_column(SAEnum(ReminderPriority, name="reminder_priority"), nullable=False)
    status: Mapped[ReminderStatus] = mapped_column(SAEnum(ReminderStatus, name="reminder_status"), nullable=False, default=ReminderStatus.open)
    escalation_level: Mapped[int] = mapped_column(default=0, nullable=False)
    escalated_to: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship(back_populates="reminders")
    assignee: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to])
