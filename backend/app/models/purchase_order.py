from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PODesignStatus, POStatus


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    po_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    product_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    order_quantity_pcs: Mapped[int] = mapped_column(Integer, nullable=False)
    mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    selling_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    promise_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[POStatus] = mapped_column(
        Enum(POStatus, name="po_status"),
        nullable=False,
        default=POStatus.fabric_check_pending,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fabric_design_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("fabric_designs.id"), nullable=True)
    design_name_snapshot: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    design_code_snapshot: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    design_image_url_snapshot: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    design_status: Mapped[PODesignStatus] = mapped_column(
        Enum(PODesignStatus, name="po_design_status"),
        nullable=False,
        default=PODesignStatus.not_provided,
    )
    priority_level: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, default="normal")
    priority_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority_updated_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    priority_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product: Mapped["Product"] = relationship(back_populates="purchase_orders")
    fabric_plan: Mapped[Optional["FabricPlan"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        uselist=False,
    )
    stage_summaries: Mapped[List["StageSummary"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="StageSummary.sequence",
    )
    dispatch_loads: Mapped[List["DispatchLoad"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[List["Alert"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")
    reminders: Mapped[List["Reminder"]] = relationship(cascade="all, delete-orphan")
    mill_order_requirements: Mapped[List["MillOrderRequirement"]] = relationship(cascade="all, delete-orphan")
