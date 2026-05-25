"""Per-request DB session for voice tools.

Gemini's automatic function calling only passes the args the model generates,
so tools cannot accept an AsyncSession parameter directly. Instead the REST
endpoint binds the request's session into this ContextVar before calling the
brain; tools read it with `current_session()` when they need to query the DB.

Why a ContextVar and not a module-level global: each FastAPI request runs in
its own asyncio task and ContextVars are task-local, so concurrent requests
never see each other's session.
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession


_current: ContextVar[Optional[AsyncSession]] = ContextVar("voice_current_session", default=None)


def current_session() -> AsyncSession:
    session = _current.get()
    if session is None:
        raise RuntimeError(
            "No DB session bound to the voice context. "
            "Call this tool from inside a request that ran `with use_session(session): ...`."
        )
    return session


@contextmanager
def use_session(session: AsyncSession) -> Iterator[None]:
    token: Token = _current.set(session)
    try:
        yield
    finally:
        _current.reset(token)
