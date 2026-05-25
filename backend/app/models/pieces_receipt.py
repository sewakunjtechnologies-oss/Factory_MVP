from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import GUID

from app.core.database import Base


class PiecesReceipt(Base):
    __tablename__ = "pieces_receipts"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    product_fabric_line_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("product_fabric_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pieces: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    mill_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
