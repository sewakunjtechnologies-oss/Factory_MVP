from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


_is_sqlite = settings.database_url.startswith("sqlite")

# SQLite needs StaticPool-equivalent behavior in tests, but for normal serving a
# single connection pool is fine. We just tune the pragmas below.
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    # SQLite ignores the pool size; Postgres keeps the default behaviour.
    future=True,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


# -- SQLite-specific tuning -------------------------------------------------
# Run on every new SQLite connection:
#   - WAL journal so readers don't block writers (and vice-versa).
#   - synchronous=NORMAL: durable enough, much faster than FULL.
#   - foreign_keys=ON: SQLite ships with FK enforcement OFF by default.
#   - busy_timeout: short blocking wait if another writer holds the lock,
#                   instead of an immediate "database is locked" error.
if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def create_all_tables() -> None:
    """Create every table SQLAlchemy knows about. Safe to call repeatedly —
    it's a no-op for tables that already exist. Used at startup so a fresh
    SQLite file gets the full schema with one call.

    Importing `app.models` here (rather than at module top) avoids a circular
    import: models import `Base` from this file.
    """
    from app import models  # noqa: F401  -- side-effect: registers every table

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
