from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_owner, require_owner_or_manager
from app.models.user import User
from app.services.exceptions import DomainError
from app.schemas.packing_material import (
    PackingMaterialBackfillSummary,
    PackingMaterialCategoryDemand,
    PackingMaterialCreate,
    PackingMaterialRead,
    PackingMaterialUpdate,
)
from app.services.packing_material_service import (
    backfill_june_packing_materials,
    create_packing_material,
    delete_packing_material,
    get_packing_material,
    list_category_demand,
    list_packing_materials,
    update_packing_material,
)

router = APIRouter()


@router.get("", response_model=List[PackingMaterialRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
    purchase_order_id: Optional[UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
) -> List[PackingMaterialRead]:
    return await list_packing_materials(
        db,
        purchase_order_id=purchase_order_id,
        status=status,
        search=search,
    )


@router.post("", response_model=PackingMaterialRead, status_code=201)
async def create(
    payload: PackingMaterialCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> PackingMaterialRead:
    _ensure_owner_for_owner_fields(payload.model_dump(exclude_unset=True), user)
    return await create_packing_material(db, payload, actor_id=user.id, actor_role=user.role.value)


@router.post("/backfill-june", response_model=PackingMaterialBackfillSummary)
async def backfill_june(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> PackingMaterialBackfillSummary:
    return await backfill_june_packing_materials(db)


@router.get("/category-demand", response_model=List[PackingMaterialCategoryDemand])
async def category_demand(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[PackingMaterialCategoryDemand]:
    return await list_category_demand(db)


@router.get("/{row_id}", response_model=PackingMaterialRead)
async def get_one(
    row_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> PackingMaterialRead:
    return await get_packing_material(db, row_id)


@router.patch("/{row_id}", response_model=PackingMaterialRead)
async def update_one(
    row_id: UUID,
    payload: PackingMaterialUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> PackingMaterialRead:
    _ensure_owner_for_owner_fields(payload.model_dump(exclude_unset=True), user)
    return await update_packing_material(db, row_id, payload, actor_id=user.id, actor_role=user.role.value)


@router.delete("/{row_id}", status_code=204, response_class=Response)
async def delete_one(
    row_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> Response:
    await delete_packing_material(db, row_id, actor_id=user.id, actor_role=user.role.value)
    return Response(status_code=204)


def _ensure_owner_for_owner_fields(payload: dict, user: User) -> None:
    owner_only_fields = {
        "printed_consumption_qty",
        "actual_consumption_qty",
        "printed_stock_qty",
        "actual_stock_qty",
    }
    if owner_only_fields.intersection(payload) and user.role.value != "owner":
        raise DomainError(status_code=403, detail="Only owner can edit actual/printed packing material fields")
