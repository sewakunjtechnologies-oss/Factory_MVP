from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import GUID

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    action_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    purchase_order_id: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("purchase_orders.id"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    performed_by: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    old_value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

