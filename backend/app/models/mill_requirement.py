from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MillOrderRequirementStatus(str, Enum):
    pending_mill_selection = "pending_mill_selection"
    mill_order_created = "mill_order_created"
    closed = "closed"


class MillOrderRequirement(Base):
    __tablename__ = "mill_order_requirements"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    required_meters: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    available_meters: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    shortage_meters: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    gsm: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    fabric_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    design: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    suggested_order_meters: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[MillOrderRequirementStatus] = mapped_column(
        SAEnum(MillOrderRequirementStatus, name="mill_order_requirement_status"),
        nullable=False,
        default=MillOrderRequirementStatus.pending_mill_selection,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
