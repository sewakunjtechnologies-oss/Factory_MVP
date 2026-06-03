from __future__ import annotations

from typing import List

from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_manager, require_owner, require_owner_or_manager, require_receipt_reader
from app.models.user import User
from app.schemas.fabric import FabricPlanRead
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderPriorityUpdate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
)
from app.services.fabric_planning import refresh_po_fabric_plan
from app.services.purchase_order_service import (
    create_purchase_order,
    delete_purchase_order,
    get_purchase_order,
    list_purchase_orders,
    update_purchase_order,
    update_purchase_order_priority,
)

router = APIRouter()


@router.post("", response_model=PurchaseOrderRead, status_code=201)
async def create(
    payload: PurchaseOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_owner)],
) -> PurchaseOrderRead:
    return await create_purchase_order(db, payload, current_user.id)


@router.get("", response_model=List[PurchaseOrderRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_receipt_reader)],
) -> List[PurchaseOrderRead]:
    return await list_purchase_orders(db)


@router.get("/{purchase_order_id}", response_model=PurchaseOrderRead)
async def get_one(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_receipt_reader)],
) -> PurchaseOrderRead:
    return await get_purchase_order(db, purchase_order_id)


@router.post("/{purchase_order_id}/fabric-plan/recalculate", response_model=FabricPlanRead)
async def recalculate_fabric_plan(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> FabricPlanRead:
    return await refresh_po_fabric_plan(db, purchase_order_id)


@router.post("/{purchase_order_id}/priority", response_model=PurchaseOrderRead)
async def update_priority(
    purchase_order_id: UUID,
    payload: PurchaseOrderPriorityUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> PurchaseOrderRead:
    return await update_purchase_order_priority(
        db,
        purchase_order_id=purchase_order_id,
        priority_level=payload.priority_level,
        priority_reason=payload.priority_reason,
        updated_by=user.id,
        updated_role=user.role.value,
    )


@router.patch("/{purchase_order_id}", response_model=PurchaseOrderRead)
async def update_one(
    purchase_order_id: UUID,
    payload: PurchaseOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> PurchaseOrderRead:
    fields = payload.model_dump(exclude_unset=True)
    return await update_purchase_order(
        db,
        purchase_order_id=purchase_order_id,
        fields=fields,
        updated_by=user.id,
    )


@router.delete("/{purchase_order_id}", status_code=204, response_class=Response)
async def delete_one(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner)],
) -> Response:
    await delete_purchase_order(db, purchase_order_id=purchase_order_id, deleted_by=user.id)
    return Response(status_code=204)
