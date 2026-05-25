from __future__ import annotations

import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate
from app.services.exceptions import DomainError


def _infer_width_from_size(size: str | None) -> float:
    if not size:
        return 100.0
    nums = re.findall(r"\d+(?:\.\d+)?", size)
    if not nums:
        return 100.0
    return max(float(nums[0]), 1.0)


async def create_product(db: AsyncSession, payload: ProductCreate) -> Product:
    data = payload.model_dump()
    # Width is no longer entered by the user — infer from `size`. Falls back to 100.0 default
    # when size has no leading number.
    if data.get("width") is None:
        data["width"] = Decimal(str(_infer_width_from_size(data.get("size"))))
    # Color is detected from the product photo by AI vision. Until that runs, store a sentinel
    # so the NOT NULL DB column and fabric-matching joins keep working.
    if not data.get("color"):
        data["color"] = "unspecified"
    product = Product(**data)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def list_products(db: AsyncSession) -> list[Product]:
    result = await db.execute(select(Product).order_by(Product.created_at.desc()))
    return list(result.scalars().all())


async def get_product(db: AsyncSession, product_id: UUID) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise DomainError(status_code=404, detail="Product not found")
    return product
