from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.types import GUID

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    product_category: Mapped[str] = mapped_column(String(100), nullable=False, default="bedsheet")
    size: Mapped[str] = mapped_column(String(100), nullable=False)
    design: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(80), nullable=False)
    fabric_type: Mapped[str] = mapped_column(String(120), nullable=False)
    gsm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    width: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    per_piece_fabric_usage_m: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    wastage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    roll_length_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    product_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(back_populates="product")
