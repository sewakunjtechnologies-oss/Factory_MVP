from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlertPriority, AlertType


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: Optional[UUID]
    alert_type: AlertType
    priority: AlertPriority
    title: str
    message: str
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime]
