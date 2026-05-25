from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DispatchCostType


class DispatchLoad(Base):
    __tablename__ = "dispatch_loads"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)
    load_number: Mapped[str] = mapped_column(String(100), nullable=False)
    shipped_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vehicle_identifier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expected_piece_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_loaded_pieces: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cbm_capacity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)
    cbm_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)
    cost_type: Mapped[DispatchCostType] = mapped_column(
        Enum(DispatchCostType, name="dispatch_cost_type"),
        nullable=False,
        default=DispatchCostType.invoice_percent,
    )
    invoice_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    dispatch_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    cbm_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)
    cbm_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    manual_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    vehicle_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    dispatch_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    expected_cost_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    actual_cost_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 3), nullable=True)
    shipped_at: Mapped[date] = mapped_column(Date, nullable=False)
    transporter_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tracking_reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    document_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    invoice_uploaded: Mapped[bool] = mapped_column(default=False, nullable=False)
    packing_list_uploaded: Mapped[bool] = mapped_column(default=False, nullable=False)
    eway_bill_uploaded: Mapped[bool] = mapped_column(default=False, nullable=False)
    transporter_confirmation: Mapped[bool] = mapped_column(default=False, nullable=False)
    buyer_dispatch_approval: Mapped[bool] = mapped_column(default=False, nullable=False)
    shortfall_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shortfall_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linked_repair_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    linked_alteration_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    completed_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="dispatch_loads")
