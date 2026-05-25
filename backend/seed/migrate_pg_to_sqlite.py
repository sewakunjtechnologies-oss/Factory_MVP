"""One-time data migration: Postgres -> SQLite.

Runs from the host (NOT inside the API container) because the host has psycopg
installed in a temporary venv. The script:

  1. Connects to the live Postgres (factory_postgres on :5433).
  2. Connects to the target SQLite file (created by the API container).
  3. Iterates every table in foreign-key-safe order and bulk-copies rows.
  4. Coerces Postgres-specific types (datetime with tz, UUID, enum) to SQLite-safe
     scalars on the way through.

Idempotent-ish: it does an INSERT OR IGNORE so re-running is safe — but if you
want a guaranteed clean re-run, delete the SQLite file first and let the API
recreate it.

Usage from the project root:
  python -m venv /tmp/migrate-venv
  /tmp/migrate-venv/bin/pip install sqlalchemy 'psycopg[binary]'
  /tmp/migrate-venv/bin/python backend/seed/migrate_pg_to_sqlite.py
"""

from __future__ import annotations

import sys
import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, insert, select
from sqlalchemy.engine import Engine


PG_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/factory_mvp"
SQLITE_URL = f"sqlite:///{Path(__file__).resolve().parents[1] / 'data' / 'factory.db'}"

CHUNK_SIZE = 500  # rows per insert batch — keeps memory bounded for large tables


def _coerce(value: Any) -> Any:
    """Massage one Postgres value into something SQLite + SQLAlchemy will accept.

    SQLAlchemy with stock pysqlite handles datetime/date/Decimal natively, but
    UUIDs need to be strings (our GUID column expects str on SQLite) and
    Enum/PgEnum values need their `.value` extracted.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date, bool, int, float, str, bytes, Decimal)):
        return value
    # PG enum values arrive as the enum member; SQLAlchemy stringifies them.
    if hasattr(value, "value") and not isinstance(value, (dict, list)):
        return value.value
    # Anything else (lists/dicts from JSON columns) passes through — SQLAlchemy
    # JSON columns serialize on both sides.
    return value


def _copy_table(src_engine: Engine, dst_engine: Engine, src_table, dst_table) -> int:
    with src_engine.connect() as src_conn:
        result = src_conn.execute(select(src_table))
        rows = result.fetchall()
        if not rows:
            return 0
        columns = result.keys()

    # Build dicts in chunks.
    inserted = 0
    with dst_engine.begin() as dst_conn:
        batch: list[dict] = []
        for row in rows:
            batch.append({col: _coerce(row[i]) for i, col in enumerate(columns)})
            if len(batch) >= CHUNK_SIZE:
                # `prefixes=["OR IGNORE"]` makes re-runs safe in SQLite.
                dst_conn.execute(insert(dst_table).prefix_with("OR IGNORE"), batch)
                inserted += len(batch)
                batch.clear()
        if batch:
            dst_conn.execute(insert(dst_table).prefix_with("OR IGNORE"), batch)
            inserted += len(batch)
    return inserted


def main() -> int:
    print(f"Source:  {PG_URL}")
    print(f"Target:  {SQLITE_URL}")
    print()

    src = create_engine(PG_URL, future=True)
    dst = create_engine(SQLITE_URL, future=True)

    # Reflect both schemas. We iterate from the SQLite side (it's the schema of
    # record) so the order is: tables that exist on BOTH sides. Anything in
    # Postgres but not in SQLite was already removed in the cleanup phases —
    # we skip those silently.
    src_meta = MetaData()
    dst_meta = MetaData()
    src_meta.reflect(bind=src)
    dst_meta.reflect(bind=dst)

    start = time.time()
    total = 0
    skipped: list[str] = []

    # FK-safe order: iterate dst.sorted_tables which respects foreign keys.
    for dst_table in dst_meta.sorted_tables:
        name = dst_table.name
        src_table = src_meta.tables.get(name)
        if src_table is None:
            skipped.append(f"{name} (not in Postgres)")
            continue
        try:
            n = _copy_table(src, dst, src_table, dst_table)
            print(f"  {name:35s}  {n:>6,} rows")
            total += n
        except Exception as e:  # noqa: BLE001
            print(f"  {name:35s}  FAILED — {e}", file=sys.stderr)
            return 1

    print()
    print(f"Done. Copied {total:,} rows in {time.time() - start:.1f}s.")
    if skipped:
        print(f"Skipped {len(skipped)} table(s) not present in Postgres:")
        for s in skipped:
            print(f"  - {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
