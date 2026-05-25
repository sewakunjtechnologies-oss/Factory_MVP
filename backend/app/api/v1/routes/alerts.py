from __future__ import annotations

from typing import List

from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner
from app.models.user import User
from app.schemas.alert import AlertRead
from app.services.alert_engine import generate_alerts, list_alerts, resolve_alert

router = APIRouter()


@router.post("/generate", response_model=List[AlertRead])
async def generate(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[AlertRead]:
    return await generate_alerts(db)


@router.get("", response_model=List[AlertRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
    active_only: bool = Query(default=True),
) -> List[AlertRead]:
    return await list_alerts(db, active_only)


@router.post("/{alert_id}/resolve", response_model=AlertRead)
async def resolve(
    alert_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> AlertRead:
    return await resolve_alert(db, alert_id)
