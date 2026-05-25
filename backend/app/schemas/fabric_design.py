from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import FabricDesignCategory


class FabricDesignCreate(BaseModel):
    category: FabricDesignCategory
    design_name: Optional[str] = Field(default=None, max_length=180)
    design_code: Optional[str] = Field(default=None, max_length=30)
    image_url: Optional[str] = Field(default=None, max_length=500)
    color_tags: Optional[List[str]] = None
    description: Optional[str] = Field(default=None, max_length=1000)
    is_active: bool = True


class FabricDesignUpdate(BaseModel):
    category: Optional[FabricDesignCategory] = None
    design_name: Optional[str] = Field(default=None, max_length=180)
    design_code: Optional[str] = Field(default=None, max_length=30)
    image_url: Optional[str] = Field(default=None, max_length=500)
    color_tags: Optional[List[str]] = None
    description: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None


class FabricDesignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: FabricDesignCategory
    design_name: str
    design_code: str
    image_url: Optional[str]
    color_tags: Optional[List[str]]
    description: Optional[str]
    is_active: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class FabricDesignBulkUploadResult(BaseModel):
    created: List[FabricDesignRead]
    skipped: List[str] = Field(default_factory=list)


class FabricDesignBulkUploadInput(BaseModel):
    category: FabricDesignCategory
    names: List[Optional[str]] = Field(default_factory=list)
    image_urls: List[Optional[str]] = Field(default_factory=list)


class FabricDesignUploadPhotoResponse(BaseModel):
    image_url: str


class PurchaseOrderDesignInput(BaseModel):
    fabric_design_id: Optional[UUID] = None
    custom_design_name: Optional[str] = Field(default=None, max_length=180)
    custom_design_photo_url: Optional[str] = Field(default=None, max_length=500)
    save_custom_design_to_library: bool = False

    @model_validator(mode="after")
    def validate_mode(self) -> "PurchaseOrderDesignInput":
        has_existing = self.fabric_design_id is not None
        has_custom = bool((self.custom_design_name or "").strip()) or bool((self.custom_design_photo_url or "").strip())
        if has_existing and has_custom:
            raise ValueError("Choose either an existing fabric design or a custom design, not both.")
        return self
