from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder, ReminderPriority, ReminderStatus, ReminderType
from app.schemas.reminder import ReminderCreate
from app.services.exceptions import DomainError
from app.services.notification_service import create_notification
from app.services.user_service import get_or_create_owner


async def create_reminder(db: AsyncSession, payload: ReminderCreate) -> Reminder:
    if payload.due_date is None:
        raise DomainError(status_code=400, detail="due_date is required")
    reminder = Reminder(**payload.model_dump())
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return reminder


async def upsert_reminder(
    db: AsyncSession,
    *,
    purchase_order_id: UUID | None,
    reminder_type: ReminderType,
    title: str,
    message: str,
    due_date: date,
    priority: ReminderPriority = ReminderPriority.medium,
    assigned_to: UUID | None = None,
) -> Reminder:
    result = await db.execute(
        select(Reminder).where(
            and_(
                Reminder.purchase_order_id == purchase_order_id,
                Reminder.reminder_type == reminder_type,
                Reminder.status == ReminderStatus.open,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.title = title
        existing.message = message
        existing.due_date = due_date
        existing.priority = priority
        existing.assigned_to = assigned_to
        await db.commit()
        await db.refresh(existing)
        return existing

    reminder = Reminder(
        purchase_order_id=purchase_order_id,
        reminder_type=reminder_type,
        title=title,
        message=message,
        due_date=due_date,
        priority=priority,
        assigned_to=assigned_to,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    return reminder


async def list_reminders(db: AsyncSession, status: ReminderStatus | None = ReminderStatus.open) -> list[Reminder]:
    statement = select(Reminder).order_by(Reminder.due_date, Reminder.priority.desc())
    if status is not None:
        statement = statement.where(Reminder.status == status)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def list_due_reminders(db: AsyncSession, on_date: date | None = None) -> list[Reminder]:
    today = on_date or date.today()
    result = await db.execute(
        select(Reminder)
        .where(
            Reminder.status == ReminderStatus.open,
            Reminder.due_date <= today,
        )
        .order_by(Reminder.due_date, Reminder.priority.desc())
    )
    return list(result.scalars().all())


async def complete_reminder(db: AsyncSession, reminder_id: UUID) -> Reminder:
    reminder = await db.get(Reminder, reminder_id)
    if reminder is None:
        raise DomainError(status_code=404, detail="Reminder not found")
    reminder.status = ReminderStatus.completed
    reminder.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(reminder)
    return reminder


async def escalate_overdue_reminders(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    overdue_hours: int = 24,
) -> list[Reminder]:
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(hours=max(overdue_hours, 1))
    result = await db.execute(
        select(Reminder).where(
            Reminder.status == ReminderStatus.open,
            Reminder.due_date <= current_time.date(),
            Reminder.created_at <= cutoff,
        )
    )
    owner = await get_or_create_owner(db)
    escalated: list[Reminder] = []
    for reminder in result.scalars().all():
        reminder.escalation_level += 1
        reminder.escalated_to = owner.id
        reminder.escalated_at = current_time
        reminder.escalation_reason = f"Reminder overdue beyond {overdue_hours} hours."
        escalated.append(reminder)
        await create_notification(
            db,
            user_id=owner.id,
            purchase_order_id=reminder.purchase_order_id,
            notification_type="reminder_escalated",
            title="Reminder escalated",
            message=f"{reminder.title} has been escalated to owner.",
        )
    await db.commit()
    return escalated
