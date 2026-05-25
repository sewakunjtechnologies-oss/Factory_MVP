from __future__ import annotations

from typing import List

from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner
from app.models.user import User
from app.schemas.product import ProductCreate, ProductRead
from app.services.product_service import create_product, get_product, list_products

router = APIRouter()


@router.post("", response_model=ProductRead, status_code=201)
async def create(
    payload: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> ProductRead:
    return await create_product(db, payload)


@router.get("", response_model=List[ProductRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[ProductRead]:
    return await list_products(db)


@router.get("/{product_id}", response_model=ProductRead)
async def get_one(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> ProductRead:
    return await get_product(db, product_id)
