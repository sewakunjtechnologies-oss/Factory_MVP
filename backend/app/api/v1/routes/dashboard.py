from __future__ import annotations

from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner
from app.models.user import User
from app.schemas.dashboard import OwnerDashboardRead
from app.services.dashboard_service import get_owner_dashboard

router = APIRouter()


@router.get("/owner", response_model=OwnerDashboardRead)
async def owner(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> OwnerDashboardRead:
    return await get_owner_dashboard(db)
