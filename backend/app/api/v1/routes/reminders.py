from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_manager, require_owner
from app.models.reminder import ReminderStatus
from app.models.user import User
from app.schemas.reminder import ReminderCreate, ReminderRead
from app.services.reminder_service import (
    complete_reminder,
    create_reminder,
    escalate_overdue_reminders,
    list_due_reminders,
    list_reminders,
)
from app.services.shortage_reminders import run_daily_shortage_check

router = APIRouter()


@router.post("", response_model=ReminderRead, status_code=201)
async def create(
    payload: ReminderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> ReminderRead:
    return await create_reminder(db, payload)


@router.get("", response_model=List[ReminderRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
    status: Optional[ReminderStatus] = Query(default=ReminderStatus.open),
) -> List[ReminderRead]:
    return await list_reminders(db, status=status)


@router.get("/due", response_model=List[ReminderRead])
async def due(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[ReminderRead]:
    return await list_due_reminders(db)


@router.post("/{reminder_id}/complete", response_model=ReminderRead)
async def complete(
    reminder_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> ReminderRead:
    return await complete_reminder(db, reminder_id)


@router.post("/escalate")
async def escalate(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_manager)],
) -> Dict[str, int]:
    escalated = await escalate_overdue_reminders(db)
    return {"escalated_count": len(escalated)}


@router.post("/check-shortages")
async def check_shortages(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_manager)],
) -> Dict[str, int]:
    """Run the daily mill / stitching / fabric shortage check on demand."""
    return await run_daily_shortage_check(db)
