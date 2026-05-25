from __future__ import annotations

import json
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_manager, require_owner
from app.models.enums import FabricDesignCategory
from app.models.user import User
from app.schemas.fabric_design import (
    FabricDesignBulkUploadResult,
    FabricDesignCreate,
    FabricDesignRead,
    FabricDesignUpdate,
    FabricDesignUploadPhotoResponse,
)
from app.services.fabric_design_service import (
    create_fabric_design,
    deactivate_fabric_design,
    list_fabric_designs,
    resolve_upload_path,
    save_design_upload,
    update_fabric_design,
    get_fabric_design,
)

router = APIRouter()


@router.post("", response_model=FabricDesignRead, status_code=201)
async def create_design(
    payload: FabricDesignCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_manager)],
) -> FabricDesignRead:
    return await create_fabric_design(db, payload, created_by=current_user.id)


@router.get("", response_model=List[FabricDesignRead])
async def list_designs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_manager)],
    category: Optional[FabricDesignCategory] = Query(default=None),
    search: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=True),
) -> List[FabricDesignRead]:
    return await list_fabric_designs(db, category=category, search=search, is_active=is_active)


@router.get("/files/{filename}")
async def get_design_photo(filename: str) -> FileResponse:
    return FileResponse(path=str(resolve_upload_path(filename)))


@router.post("/upload-photo", response_model=FabricDesignUploadPhotoResponse)
async def upload_design_photo(
    _: Annotated[User, Depends(require_manager)],
    file: UploadFile = File(...),
) -> FabricDesignUploadPhotoResponse:
    image_url = await save_design_upload(file)
    return FabricDesignUploadPhotoResponse(image_url=image_url)


@router.get("/{design_id}", response_model=FabricDesignRead)
async def get_design(
    design_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_manager)],
) -> FabricDesignRead:
    return await get_fabric_design(db, design_id)


@router.patch("/{design_id}", response_model=FabricDesignRead)
async def update_design(
    design_id: UUID,
    payload: FabricDesignUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_manager)],
) -> FabricDesignRead:
    return await update_fabric_design(db, design_id, payload)


@router.delete("/{design_id}", response_model=FabricDesignRead)
async def deactivate_design(
    design_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> FabricDesignRead:
    return await deactivate_fabric_design(db, design_id)


@router.post("/bulk-upload", response_model=FabricDesignBulkUploadResult, status_code=201)
async def bulk_upload_designs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_manager)],
    category: FabricDesignCategory = Form(...),
    files: List[UploadFile] = File(...),
    names_json: Optional[str] = Form(default=None),
) -> FabricDesignBulkUploadResult:
    names: list[str | None] = []
    if names_json:
        try:
            parsed = json.loads(names_json)
            if isinstance(parsed, list):
                names = [str(item).strip() if item is not None else None for item in parsed]
        except json.JSONDecodeError:
            names = []

    created: list[FabricDesignRead] = []
    skipped: list[str] = []
    for index, item in enumerate(files):
        image_url = await save_design_upload(item)
        name = names[index] if index < len(names) else None
        payload = FabricDesignCreate(
            category=category,
            design_name=name or None,
            image_url=image_url,
            is_active=True,
        )
        row = await create_fabric_design(db, payload, created_by=current_user.id, commit=False)
        created.append(FabricDesignRead.model_validate(row))
        if not name:
            skipped.append(item.filename or f"file_{index+1}")
    await db.commit()
    return FabricDesignBulkUploadResult(created=created, skipped=skipped)
