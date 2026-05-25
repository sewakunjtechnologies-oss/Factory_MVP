"""DB-agnostic column types.

`GUID` is a UUID column that emits Postgres' native UUID on Postgres dialects
and a 36-char string on SQLite. Lets the same SQLAlchemy models run unchanged
against both, which is what makes the Postgres -> SQLite migration painless.

`JSON_TEXT` is a JSON column that uses PG's JSONB on Postgres and SQLite's
TEXT-backed JSON elsewhere. Either way, Python sees a dict/list.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CHAR, JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID_TYPE


class GUID(TypeDecorator):
    """Platform-independent UUID column.

    - Postgres: stored as native ``uuid``.
    - Everything else (SQLite): stored as ``CHAR(36)`` lowercase string.

    Python always sees a ``uuid.UUID`` instance.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID_TYPE(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSON_TEXT(TypeDecorator):
    """JSON column that uses native JSONB on Postgres, TEXT-backed JSON on SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(JSON())
