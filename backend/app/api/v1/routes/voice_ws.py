"""Phase 3 — WebSocket entry point for the live voice assistant.

Endpoint: WS /api/v1/voice/stream?token=<jwt>

Auth is via JWT in the query string because browsers don't let us set custom
headers on a WebSocket handshake. The token is validated before `accept()`;
unauthorised attempts are closed with policy-violation code 1008.

Once authorised this hands the connection + DB session to
`services.voice.live.run_live_session()`, which runs until either side
disconnects or an error halts the audio pumps.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.config import settings
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.voice.live import run_live_session


router = APIRouter()


async def _resolve_owner(token: str, db: AsyncSession) -> User | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = payload.get("sub")
        user_id = UUID(subject) if subject else None
    except (JWTError, ValueError):
        return None
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    if user.role not in (UserRole.owner, UserRole.admin):
        return None
    return user


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    token: Annotated[str, Query(min_length=10)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    user = await _resolve_owner(token, db)
    if user is None:
        # Policy violation per RFC 6455 §7.4.1 — token bad or user not owner.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    await run_live_session(websocket, db)
