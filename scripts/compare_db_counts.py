#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

TABLES = [
    "users",
    "purchase_orders",
    "products",
    "fabric_plans",
    "fabric_mill_orders",
    "dispatch_loads",
    "alerts",
    "reminders",
    "report_requests",
    "vehicles",
]


def counts(db_path: Path) -> dict[str, int | str]:
    conn = sqlite3.connect(db_path)
    try:
        out: dict[str, int | str] = {}
        for table in TABLES:
            try:
                out[table] = conn.execute(f"select count(*) from {table}").fetchone()[0]
            except sqlite3.Error as exc:
                out[table] = f"missing/error: {exc}"
        return out
    finally:
        conn.close()


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print("Usage: scripts/compare_db_counts.py local.db [cloud-or-restored.db]", file=sys.stderr)
        return 2
    first = counts(Path(sys.argv[1]))
    print(f"Counts for {sys.argv[1]}")
    for table, count in first.items():
        print(f"{table}: {count}")
    if len(sys.argv) == 3:
        second = counts(Path(sys.argv[2]))
        print(f"\nCounts for {sys.argv[2]}")
        for table, count in second.items():
            marker = "OK" if first.get(table) == count else "DIFF"
            print(f"{table}: {count} [{marker}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
