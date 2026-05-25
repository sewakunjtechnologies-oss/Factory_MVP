from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationRead
from app.services.notification_service import list_notifications, mark_notification_read

router = APIRouter()


@router.get("", response_model=List[NotificationRead])
async def list_user_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    unread: bool = Query(default=False),
) -> List[NotificationRead]:
    return await list_notifications(db, user.id, unread)


@router.post("/{notification_id}/read", response_model=Optional[NotificationRead])
async def mark_read(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Optional[NotificationRead]:
    return await mark_notification_read(db, notification_id, user.id)
