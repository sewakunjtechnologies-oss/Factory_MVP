from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID


class PackingMaterialInventory(Base):
    __tablename__ = "packing_material_inventory"
    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "material_name",
            name="uq_packing_material_po_material",
        ),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("purchase_orders.id"), nullable=True)
    po_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    category_name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    material_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    material_type: Mapped[str] = mapped_column(String(60), nullable=False, default="other")
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="pcs")
    required_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    in_stock_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    consumed_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    printed_consumption_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    actual_consumption_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    printed_stock_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    actual_stock_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    shortage_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    supplier_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
