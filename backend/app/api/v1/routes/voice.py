"""Voice/text assistant endpoints.

POST /api/v1/voice/ask  — typed question or transcribed-speech question. Runs
Gemini brain with the tool catalog (PDF generation, fabric/PO/dispatch lookups,
PO feasibility, etc.) and returns the text answer plus any artifacts the tools
produced (e.g. a generated PDF's download URL).

Errors from Gemini (rate limits, model overloads, auth) are translated to clean
HTTP responses so the frontend can show a useful toast instead of a generic
"Network error".
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors as genai_errors
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_owner_or_manager
from app.models.user import User
from app.services.voice import artifacts_scope, ask_async, use_session

logger = logging.getLogger(__name__)
router = APIRouter()


class VoiceAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class VoiceArtifact(BaseModel):
    type: str
    title: str | None = None
    download_url: str | None = None
    report_type: str | None = None
    report_id: str | None = None


class VoiceAskResponse(BaseModel):
    answer: str
    artifacts: List[VoiceArtifact] = Field(default_factory=list)


_GEMINI_USER_MESSAGES = {
    401: "The assistant is misconfigured (Gemini auth). Check the GEMINI_API_KEY env var.",
    403: "Gemini refused the request — check API quota and key permissions.",
    429: "The assistant is rate-limited right now. Please try again in a few seconds.",
    500: "Gemini is temporarily unavailable. Please try again.",
    502: "Gemini is temporarily unavailable. Please try again.",
    503: "The assistant is busy right now (model overloaded). Please try again in a few seconds.",
    504: "Gemini timed out. Please try again.",
}


@router.post("/ask", response_model=VoiceAskResponse)
async def ask_voice_assistant(
    payload: VoiceAskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> VoiceAskResponse:
    try:
        with use_session(db):
            with artifacts_scope() as sink:
                answer = await ask_async(payload.message)
                artifacts = list(sink)
    except genai_errors.APIError as error:
        # Covers ClientError (4xx) + ServerError (5xx) + any future subclass.
        code = getattr(error, "code", 502) or 502
        # Map to a 502 so the frontend treats this as a service-availability
        # problem (retryable) rather than a request error. We pass the
        # user-friendly message through to the UI.
        detail = _GEMINI_USER_MESSAGES.get(code, "The assistant could not respond. Please try again.")
        logger.warning("voice/ask: Gemini returned %s — %s", code, error)
        raise HTTPException(status_code=502, detail=detail) from error
    except Exception as error:  # noqa: BLE001
        logger.exception("voice/ask: unexpected failure")
        raise HTTPException(status_code=500, detail="The assistant hit an unexpected error.") from error
    return VoiceAskResponse(
        answer=answer,
        artifacts=[VoiceArtifact.model_validate(item) for item in artifacts],
    )
