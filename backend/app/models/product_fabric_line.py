from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProductFabricLine(Base):
    __tablename__ = "product_fabric_lines"
    __table_args__ = (UniqueConstraint("product_id", "fabric_code", name="product_fabric_lines_unique"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fabric_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    pieces: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pieces_in_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pieces_short: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    per_piece_meters: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False, default=0)
    stock_meters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    # Bale spec — used by the dispatch CBM planner.
    pieces_per_bale: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bale_size_cbm: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    bale_weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    cutting: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    stitching: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    packing: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    dispatch: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product = relationship("Product")
