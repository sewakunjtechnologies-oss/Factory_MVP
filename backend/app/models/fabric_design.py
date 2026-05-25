from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import GUID

from app.core.database import Base
from app.models.enums import FabricDesignCategory


class FabricDesign(Base):
    __tablename__ = "fabric_designs"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    category: Mapped[FabricDesignCategory] = mapped_column(Enum(FabricDesignCategory, name="fabric_design_category"), nullable=False)
    design_name: Mapped[str] = mapped_column(String(180), nullable=False)
    design_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    color_tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
