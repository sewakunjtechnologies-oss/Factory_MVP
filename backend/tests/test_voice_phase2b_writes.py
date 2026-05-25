"""Tests for the three write tools (PO notes, mill order, stage progress).

Each tool follows the same two-step contract:
  - confirmed=False → returns a preview dict, no DB mutation
  - confirmed=True  → calls session.commit()

We use a stub AsyncSession that records `execute` calls and `commit` calls so
the tests can verify both the no-write and write paths without a real Postgres.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.services.voice import use_session
from app.services.voice.actions.mill_actions import place_mill_order
from app.services.voice.actions.po_actions import update_po_notes
from app.services.voice.actions.stage_actions import record_stage_progress
from app.services.voice.tools import get_tool


class _Result:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _StubSession:
    """Records execute/commit/add calls; returns a queued row for each execute()."""

    def __init__(self, queued_rows: list):
        self._queue = list(queued_rows)
        self.added = []
        self.commit_count = 0
        self.refresh_count = 0

    async def execute(self, _stmt):
        return _Result(self._queue.pop(0) if self._queue else None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, obj, *_a, **_k):
        self.refresh_count += 1


def _po(po_number="PO-2026-0042", notes=None, id_="1111"):
    return SimpleNamespace(id=id_, po_number=po_number, notes=notes)


# ---------- write-tool registry metadata ----------


def test_write_tools_flagged_for_confirmation() -> None:
    for name in ("update_po_notes", "place_mill_order", "record_stage_progress"):
        spec = get_tool(name)
        assert spec is not None, f"{name} should be registered"
        assert spec.requires_confirmation is True, f"{name} must require confirmation"


# ---------- update_po_notes ----------


def test_update_po_notes_preview_when_not_confirmed() -> None:
    session = _StubSession([_po(notes="old line")])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(update_po_notes(po_number="PO-2026-0042", note="will ship Monday"))
    assert out["requires_confirmation"] is True
    assert "will ship Monday" in out["preview"]
    assert session.commit_count == 0, "preview must not commit"


def test_update_po_notes_writes_when_confirmed() -> None:
    po = _po(notes="prior note")
    session = _StubSession([po])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(update_po_notes(po_number="PO-2026-0042", note="fresh note", confirmed=True))
    assert out["done"] is True
    assert session.commit_count == 1
    assert "fresh note" in po.notes
    assert "prior note" in po.notes


def test_update_po_notes_rejects_missing_po() -> None:
    session = _StubSession([None])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(update_po_notes(po_number="PO-NOPE", note="x", confirmed=True))
    assert out["found"] is False
    assert session.commit_count == 0


# ---------- place_mill_order ----------


def test_place_mill_order_preview_when_not_confirmed() -> None:
    session = _StubSession([_po()])
    tomorrow = (date.today() + timedelta(days=14)).isoformat()
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            place_mill_order(
                po_number="PO-2026-0042",
                mill_name="Sharma Mills",
                meters=500,
                committed_delivery_date_iso=tomorrow,
            )
        )
    assert out["requires_confirmation"] is True
    assert "Sharma Mills" in out["preview"]
    assert session.commit_count == 0
    assert session.added == []


def test_place_mill_order_writes_when_confirmed() -> None:
    session = _StubSession([_po()])
    delivery = (date.today() + timedelta(days=10)).isoformat()
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            place_mill_order(
                po_number="PO-2026-0042",
                mill_name="Sharma Mills",
                meters=500,
                committed_delivery_date_iso=delivery,
                confirmed=True,
            )
        )
    assert out["done"] is True
    assert session.commit_count == 1
    assert len(session.added) == 1
    assert session.added[0].mill_name == "Sharma Mills"


def test_place_mill_order_rejects_zero_meters() -> None:
    session = _StubSession([])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            place_mill_order(
                po_number="PO-X",
                mill_name="Any",
                meters=0,
                committed_delivery_date_iso="2026-12-01",
            )
        )
    assert "error" in out
    assert session.commit_count == 0


def test_place_mill_order_rejects_past_date() -> None:
    session = _StubSession([])
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            place_mill_order(
                po_number="PO-X",
                mill_name="Any",
                meters=100,
                committed_delivery_date_iso=yesterday,
            )
        )
    assert "error" in out
    assert "past" in out["error"].lower()


# ---------- record_stage_progress ----------


def test_record_stage_progress_preview_when_not_confirmed() -> None:
    from app.models.enums import StageStatus

    po = _po()
    summary = SimpleNamespace(
        id="2222",
        approved_qty=0,
        rejected_qty=0,
        completed_qty=0,
        status=StageStatus.not_started,
    )
    session = _StubSession([po, summary])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            record_stage_progress(
                po_number="PO-2026-0042",
                stage="cutting",
                approved_today=500,
            )
        )
    assert out["requires_confirmation"] is True
    assert "500 approved" in out["preview"]
    assert session.commit_count == 0


def test_record_stage_progress_writes_and_updates_summary() -> None:
    from app.models.enums import StageStatus

    po = _po()
    summary = SimpleNamespace(
        id="2222",
        approved_qty=100,
        rejected_qty=0,
        completed_qty=100,
        status=StageStatus.not_started,
    )
    session = _StubSession([po, summary])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            record_stage_progress(
                po_number="PO-2026-0042",
                stage="cutting",
                approved_today=400,
                rejected_today=10,
                confirmed=True,
            )
        )
    assert out["done"] is True
    assert session.commit_count == 1
    assert summary.approved_qty == 500
    assert summary.rejected_qty == 10
    assert summary.completed_qty == 510
    # Stage moved to in_progress because we recorded progress against a not_started one.
    assert summary.status == StageStatus.in_progress


def test_record_stage_progress_rejects_unknown_stage() -> None:
    session = _StubSession([])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            record_stage_progress(
                po_number="PO-X",
                stage="weaving",
                approved_today=10,
            )
        )
    assert "error" in out
    assert "cutting" in out["valid_stages"]


def test_record_stage_progress_rejects_no_quantities() -> None:
    session = _StubSession([])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(
            record_stage_progress(
                po_number="PO-X",
                stage="cutting",
                approved_today=0,
                rejected_today=0,
            )
        )
    assert "error" in out
