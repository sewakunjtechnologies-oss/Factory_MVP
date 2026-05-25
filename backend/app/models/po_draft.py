from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum as SAEnum, Float, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import GUID

from app.core.database import Base


class PODraftStatus(str, Enum):
    draft = "draft"
    needs_review = "needs_review"
    confirmed = "confirmed"
    rejected = "rejected"


class PODraft(Base):
    __tablename__ = "po_drafts"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    raw_input_text: Mapped[str] = mapped_column(Text, nullable=False)
    po_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity_pieces: Mapped[Optional[int]] = mapped_column(nullable=True)
    order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    shipment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    mrp_on_package: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    selling_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    design: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    product_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gsm: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    meter_per_piece: Mapped[Optional[float]] = mapped_column(Numeric(12, 3), nullable=True)
    wastage_percent: Mapped[Optional[float]] = mapped_column(Numeric(7, 4), nullable=True)
    product_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    extracted_fields_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    missing_fields_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[PODraftStatus] = mapped_column(SAEnum(PODraftStatus, name="po_draft_status"), nullable=False, default=PODraftStatus.draft)
    created_by: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
