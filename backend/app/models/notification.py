from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import GUID

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    purchase_order_id: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("purchase_orders.id"), nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

