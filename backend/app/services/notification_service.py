from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def create_notification(
    db: AsyncSession,
    *,
    user_id: UUID,
    notification_type: str,
    title: str,
    message: str,
    purchase_order_id: UUID | None = None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        purchase_order_id=purchase_order_id,
        notification_type=notification_type,
        title=title,
        message=message,
    )
    db.add(row)
    await db.flush()
    return row


async def list_notifications(db: AsyncSession, user_id: UUID, only_unread: bool = False) -> list[Notification]:
    statement = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
    if only_unread:
        statement = statement.where(Notification.is_read.is_(False))
    result = await db.execute(statement)
    return list(result.scalars().all())


async def mark_notification_read(db: AsyncSession, notification_id: UUID, user_id: UUID) -> Optional[Notification]:
    row = await db.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        return None
    row.is_read = True
    row.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row

