from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fabric_design import FabricDesign
from app.models.enums import FabricDesignCategory
from app.schemas.fabric_design import FabricDesignCreate, FabricDesignUpdate
from app.services.exceptions import DomainError


UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "fabric_designs"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

CATEGORY_PREFIX = {
    FabricDesignCategory.double_bed_sheet: "DBL",
    FabricDesignCategory.single_bed_sheet: "SGL",
    FabricDesignCategory.fitted_bed_sheet: "FIT",
    FabricDesignCategory.king_bed_sheet: "KNG",
    FabricDesignCategory.pillow: "PIL",
    FabricDesignCategory.other: "OTH",
}


def normalize_design_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", code.upper().strip())


def normalize_category(raw: str | FabricDesignCategory | None) -> FabricDesignCategory:
    if isinstance(raw, FabricDesignCategory):
        return raw
    value = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"double_bedsheet", "double_bed_sheet"}:
        return FabricDesignCategory.double_bed_sheet
    if value in {"single_bedsheet", "single_bed_sheet"}:
        return FabricDesignCategory.single_bed_sheet
    if value in {"fitted_bedsheet", "fitted_bed_sheet", "fitted_sheet"}:
        return FabricDesignCategory.fitted_bed_sheet
    if value in {"king_bedsheet", "king_bed_sheet"}:
        return FabricDesignCategory.king_bed_sheet
    if value == "pillow":
        return FabricDesignCategory.pillow
    return FabricDesignCategory.other


def next_design_code_from_existing(category: FabricDesignCategory, existing_codes: Iterable[str]) -> str:
    prefix = CATEGORY_PREFIX[category]
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    max_number = 0
    for code in existing_codes:
        match = pattern.match(code.upper())
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"{prefix}-{max_number + 1:03d}"


async def generate_next_design_code(db: AsyncSession, category: FabricDesignCategory) -> str:
    prefix = CATEGORY_PREFIX[category]
    result = await db.execute(select(FabricDesign.design_code).where(FabricDesign.design_code.ilike(f"{prefix}-%")))
    return next_design_code_from_existing(category, [code for code in result.scalars().all() if code])


async def _ensure_unique_code(db: AsyncSession, design_code: str, exclude_id: UUID | None = None) -> None:
    statement = select(FabricDesign.id).where(func.upper(FabricDesign.design_code) == design_code.upper())
    if exclude_id is not None:
        statement = statement.where(FabricDesign.id != exclude_id)
    row = await db.execute(statement)
    if row.scalar_one_or_none() is not None:
        raise DomainError(status_code=409, detail="Design code already exists")


async def create_fabric_design(
    db: AsyncSession,
    payload: FabricDesignCreate,
    *,
    created_by: UUID | None,
    commit: bool = True,
) -> FabricDesign:
    category = normalize_category(payload.category)
    design_code = normalize_design_code(payload.design_code) if payload.design_code else await generate_next_design_code(db, category)
    await _ensure_unique_code(db, design_code)
    design_name = (payload.design_name or "").strip() or design_code
    row = FabricDesign(
        category=category,
        design_name=design_name,
        design_code=design_code,
        image_url=payload.image_url,
        color_tags=payload.color_tags,
        description=payload.description,
        is_active=payload.is_active,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    if commit:
        await db.commit()
        await db.refresh(row)
    return row


async def get_fabric_design(db: AsyncSession, design_id: UUID) -> FabricDesign:
    row = await db.get(FabricDesign, design_id)
    if row is None:
        raise DomainError(status_code=404, detail="Fabric design not found")
    return row


async def list_fabric_designs(
    db: AsyncSession,
    *,
    category: FabricDesignCategory | None = None,
    search: str | None = None,
    is_active: bool | None = True,
) -> list[FabricDesign]:
    statement = select(FabricDesign).order_by(FabricDesign.design_code.asc())
    if category is not None:
        statement = statement.where(FabricDesign.category == normalize_category(category))
    if is_active is not None:
        statement = statement.where(FabricDesign.is_active.is_(is_active))
    if search:
        text = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                FabricDesign.design_name.ilike(text),
                FabricDesign.design_code.ilike(text),
                FabricDesign.description.ilike(text),
            )
        )
    result = await db.execute(statement)
    return list(result.scalars().all())


async def update_fabric_design(db: AsyncSession, design_id: UUID, payload: FabricDesignUpdate) -> FabricDesign:
    row = await get_fabric_design(db, design_id)
    data = payload.model_dump(exclude_unset=True)
    if "category" in data and data["category"] is not None:
        row.category = normalize_category(data["category"])
    if "design_code" in data and data["design_code"]:
        design_code = normalize_design_code(data["design_code"])
        await _ensure_unique_code(db, design_code, exclude_id=row.id)
        row.design_code = design_code
    if "design_name" in data and data["design_name"] is not None:
        row.design_name = data["design_name"].strip() or row.design_code
    if "image_url" in data:
        row.image_url = data["image_url"]
    if "color_tags" in data:
        row.color_tags = data["color_tags"]
    if "description" in data:
        row.description = data["description"]
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    await db.commit()
    await db.refresh(row)
    return row


async def deactivate_fabric_design(db: AsyncSession, design_id: UUID) -> FabricDesign:
    row = await get_fabric_design(db, design_id)
    row.is_active = False
    await db.commit()
    await db.refresh(row)
    return row


async def save_design_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise DomainError(status_code=400, detail="Unsupported image format")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise DomainError(status_code=400, detail="Image file too large")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    path = UPLOAD_DIR / filename
    path.write_bytes(data)
    return f"/api/v1/fabric-designs/files/{filename}"


def resolve_upload_path(filename: str) -> Path:
    target = (UPLOAD_DIR / filename).resolve()
    root = UPLOAD_DIR.resolve()
    if not str(target).startswith(str(root)):
        raise DomainError(status_code=400, detail="Invalid file path")
    if not target.exists():
        raise DomainError(status_code=404, detail="Design image not found")
    return target
