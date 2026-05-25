from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import ContractorType


class ContractorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contractor_type: ContractorType
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[EmailStr] = None


class ContractorRead(ContractorCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
