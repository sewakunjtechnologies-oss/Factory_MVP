from __future__ import annotations

from typing import List

from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner
from app.models.user import User
from app.schemas.fabric import FabricPlanRead
from app.services.fabric_planning import list_shortage_plans

router = APIRouter()


@router.get("", response_model=List[FabricPlanRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[FabricPlanRead]:
    return await list_shortage_plans(db)
