from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class MobileCategoryOption(BaseModel):
    id: UUID
    product_id: UUID
    category_name: str
    fabric_code: str
    searchable_text: str
    per_piece_meters: Decimal
    stock_meters: Decimal
    pieces_in_stock: int


class MobilePOCreate(BaseModel):
    category_option_id: UUID
    quantity: int = Field(gt=0)
    delivery_mode: Literal["month", "date"] = "month"
    delivery_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    delivery_date: date | None = None

    @model_validator(mode="after")
    def validate_delivery(self) -> "MobilePOCreate":
        if self.delivery_mode == "month" and not self.delivery_month:
            raise ValueError("delivery_month is required when delivery_mode is month")
        if self.delivery_mode == "date" and self.delivery_date is None:
            raise ValueError("delivery_date is required when delivery_mode is date")
        return self


class MobilePOCard(BaseModel):
    id: UUID
    po_number: str
    category_name: str
    fabric_code: str | None = None
    quantity: int
    delivery_date: date
    delivery_label: str
    current_stage: str
    status: str
    warning: str | None = None
    is_historical: bool = False
    next_action_label: str
    required_fabric_m: Decimal | None = None
    available_fabric_m: Decimal | None = None
    shortage_m: Decimal | None = None


class MobileHomeSummary(BaseModel):
    active_pos: int
    urgent_attention_count: int
    expected_arrivals_today: int
    ready_for_dispatch_count: int
    cards: list[MobilePOCard]


class MobileTransitionPreview(BaseModel):
    po_id: UUID
    po_number: str
    current_stage: str
    next_stage: str
    action_label: str
    required_fields: list[dict[str, Any]]
    can_execute: bool
    message: str


class MobileTransitionRequest(BaseModel):
    action: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class MobileTransitionResult(BaseModel):
    success: bool
    message: str
    card: MobilePOCard | None = None
    preview: MobileTransitionPreview | None = None


class MobileReminderAction(BaseModel):
    hours: int | None = Field(default=None, gt=0)
    until_date: date | None = None
