from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.reminder import ReminderPriority, ReminderStatus, ReminderType


class ReminderCreate(BaseModel):
    purchase_order_id: Optional[UUID] = None
    reminder_type: ReminderType
    title: str = Field(min_length=1, max_length=150)
    message: str = Field(min_length=1, max_length=500)
    due_date: date
    assigned_to: Optional[UUID] = None
    priority: ReminderPriority = ReminderPriority.medium
    status: ReminderStatus = ReminderStatus.open


class ReminderRead(ReminderCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    escalation_level: int
    escalated_to: Optional[UUID]
    escalated_at: Optional[datetime]
    escalation_reason: Optional[str]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ReminderCompleteRequest(BaseModel):
    remarks: Optional[str] = Field(default=None, max_length=500)
