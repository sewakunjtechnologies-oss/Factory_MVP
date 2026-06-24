from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner_or_manager
from app.models.user import User
from app.schemas.mobile import MobileCategoryOption, MobileHomeSummary, MobilePOCard, MobilePOCreate, MobileReminderAction, MobileTransitionPreview, MobileTransitionRequest, MobileTransitionResult
from app.services.mobile_workflow import create_mobile_po, execute_transition, get_mobile_home, get_mobile_reminder_summary, get_transition_preview, list_mobile_category_options, list_mobile_pos, mark_mobile_reminder_handled, snooze_mobile_reminder

router = APIRouter()


@router.get("/category-options", response_model=list[MobileCategoryOption])
async def category_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> list[MobileCategoryOption]:
    return await list_mobile_category_options(db)


@router.get("/home", response_model=MobileHomeSummary)
async def home(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> MobileHomeSummary:
    return await get_mobile_home(db)


@router.get("/pos", response_model=list[MobilePOCard])
async def pos(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> list[MobilePOCard]:
    return await list_mobile_pos(db)


@router.post("/pos", response_model=MobilePOCard, status_code=201)
async def create_po(
    payload: MobilePOCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> MobilePOCard:
    return await create_mobile_po(db, payload, user.id)


@router.get("/pos/{po_id}/transition", response_model=MobileTransitionPreview)
async def transition_preview(
    po_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
    action: str | None = Query(default=None),
) -> MobileTransitionPreview:
    return await get_transition_preview(db, po_id, action)


@router.post("/pos/{po_id}/transition", response_model=MobileTransitionResult)
async def transition(
    po_id: UUID,
    payload: MobileTransitionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> MobileTransitionResult:
    return await execute_transition(db, po_id, action=payload.action, values=payload.values, confirmed=payload.confirm, actor_id=user.id)


@router.get("/reminders/summary")
async def reminder_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> list[dict[str, str]]:
    return await get_mobile_reminder_summary(db)


@router.post("/reminders/{reminder_id}/snooze")
async def snooze_reminder(
    reminder_id: UUID,
    payload: MobileReminderAction,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> dict[str, str]:
    return await snooze_mobile_reminder(db, reminder_id, hours=payload.hours, until_date=payload.until_date, actor_id=user.id)


@router.post("/reminders/{reminder_id}/handled")
async def handle_reminder(
    reminder_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_owner_or_manager)],
) -> dict[str, str]:
    return await mark_mobile_reminder_handled(db, reminder_id, user.id)
