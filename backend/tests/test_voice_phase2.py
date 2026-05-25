"""Phase 2 tests for the voice assistant framework — DB-backed tools.

Strategy:
- Verify tool registration without making any API or DB call.
- Verify each tool talks to the DB through `current_session()` using a stub
  AsyncSession (so we don't need a Postgres test container yet). Real DB
  integration will be added when we add a proper conftest with a transactional
  test database.
- Optionally run a live Gemini round-trip if a key + quota are available;
  otherwise skip.
"""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.services.voice import use_session
from app.services.voice.actions.contractor_actions import find_contractor
from app.services.voice.actions.dispatch_actions import list_todays_dispatches
from app.services.voice.actions.fabric_actions import get_fabric_stock
from app.services.voice.tools import registered_names


class _StubResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _StubSession:
    """Async-compatible stub of AsyncSession that returns pre-canned rows."""

    def __init__(self, rows):
        self._rows = rows
        self.executed_stmts: list = []

    async def execute(self, stmt):
        self.executed_stmts.append(stmt)
        return _StubResult(self._rows)


def test_phase2_tools_are_registered() -> None:
    names = set(registered_names())
    assert {"get_fabric_stock", "list_todays_dispatches", "find_contractor"}.issubset(names)


def test_fabric_stock_aggregates_total() -> None:
    rows = [
        SimpleNamespace(fabric_type="cotton", color="white", gsm=150, width=90, available_length_m=200),
        SimpleNamespace(fabric_type="cotton", color="white", gsm=150, width=90, available_length_m=50.5),
    ]
    session = _StubSession(rows)
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(get_fabric_stock(fabric_type="cotton", color="white", gsm=150.0))
    assert out["match_count"] == 2
    assert out["total_meters"] == pytest.approx(250.5)
    assert out["filters_applied"] == {"fabric_type": "cotton", "color": "white", "gsm": 150.0}


def test_fabric_stock_empty_match() -> None:
    session = _StubSession([])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(get_fabric_stock(fabric_type="polyester"))
    assert out["match_count"] == 0
    assert out["total_meters"] == 0
    assert out["lots"] == []


def test_list_todays_dispatches_shape() -> None:
    po = SimpleNamespace(po_number="PO-2026-0042")
    load = SimpleNamespace(
        load_number="LD-001",
        purchase_order=po,
        shipped_qty=300,
        vehicle_identifier="HR-55-1234",
        transporter_name="Sharma Transport",
        destination="Mumbai",
        dispatch_cost=2500,
    )
    session = _StubSession([load])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(list_todays_dispatches())
    assert out["count"] == 1
    assert out["total_pieces_shipped"] == 300
    assert out["loads"][0]["po_number"] == "PO-2026-0042"
    assert out["loads"][0]["transporter_name"] == "Sharma Transport"


def test_find_contractor_rejects_invalid_type() -> None:
    session = _StubSession([])
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(find_contractor(contractor_type="weaving"))
    assert out["count"] == 0
    assert out["invalid_type"] is True
    # Returned valid types list should include the canonical stitching/cutting/etc.
    assert "stitching" in out["valid_types"]


def test_find_contractor_returns_active_rows() -> None:
    from app.models.enums import ContractorType

    rows = [
        SimpleNamespace(
            id="11111111-1111-1111-1111-111111111111",
            name="Sharma Tailors",
            contractor_type=ContractorType.stitching,
            phone="+91 90000 00001",
            email=None,
            is_active=True,
        ),
    ]
    session = _StubSession(rows)
    with use_session(session):  # type: ignore[arg-type]
        out = asyncio.run(find_contractor(contractor_type="stitching"))
    assert out["count"] == 1
    assert out["contractors"][0]["name"] == "Sharma Tailors"
    assert out["contractors"][0]["contractor_type"] == "stitching"


def test_tools_require_bound_session() -> None:
    """Without `use_session(...)` the tools must refuse, not silently fail."""
    with pytest.raises(RuntimeError, match="No DB session"):
        asyncio.run(get_fabric_stock())
