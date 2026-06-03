from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.enums import DispatchCostType
from app.schemas.dispatch import DispatchLoadCreate
from app.schemas.stage import QualityFailureCreate, StageProgressCreate
from app.services.dispatch_engine import calculate_dispatch_cost
from app.services.exceptions import DomainError
from app.services.fabric_planning import calculate_fabric_plan
from app.services.purchase_order_service import create_purchase_order


def test_po_fabric_plan_allows_missing_roll_length() -> None:
    plan = calculate_fabric_plan(
        order_qty_pcs=1000,
        per_piece_fabric_usage_m=Decimal("2.5"),
        wastage_percent=Decimal("10"),
        roll_length_m=None,
    )
    assert plan["required_m"] == Decimal("2500.000")
    assert plan["total_required_m"] == Decimal("2750.000")
    assert plan["rolls_required"] is None


def test_dispatch_costs_support_mixed_methods() -> None:
    invoice = DispatchLoadCreate(
        purchase_order_id="11111111-1111-1111-1111-111111111111",
        load_number="L1",
        shipped_qty=100,
        cost_type=DispatchCostType.invoice_percent,
        invoice_value=Decimal("50000"),
        dispatch_percent=Decimal("2.5"),
        shipped_at=date(2026, 5, 4),
    )
    cbm = DispatchLoadCreate(
        purchase_order_id="11111111-1111-1111-1111-111111111111",
        load_number="L2",
        shipped_qty=100,
        cost_type=DispatchCostType.cbm,
        cbm_value=Decimal("12.5"),
        cbm_rate=Decimal("80"),
        shipped_at=date(2026, 5, 4),
    )
    manual = DispatchLoadCreate(
        purchase_order_id="11111111-1111-1111-1111-111111111111",
        load_number="L3",
        shipped_qty=100,
        cost_type=DispatchCostType.manual,
        manual_cost=Decimal("777.77"),
        shipped_at=date(2026, 5, 4),
    )
    assert calculate_dispatch_cost(invoice) == Decimal("1250.00")
    assert calculate_dispatch_cost(cbm) == Decimal("1000.00")
    assert calculate_dispatch_cost(manual) == Decimal("777.77")


def test_daily_progress_rejects_outcome_overflow() -> None:
    with pytest.raises(ValueError, match="completed_today must equal"):
        StageProgressCreate(
            purchase_order_id="11111111-1111-1111-1111-111111111111",
            stage="stitching",
            entry_date=date(2026, 5, 4),
            completed_today=100,
            approved_today=80,
            rejected_today=30,
        )


def test_quality_failure_tracks_pending_resolution() -> None:
    failure = QualityFailureCreate(
        stage_summary_id="11111111-1111-1111-1111-111111111111",
        failed_qty=200,
        resolved_qty=75,
        action="return_to_contractor",
        reason="Measurement mismatch",
        action_date=date(2026, 5, 4),
    )
    assert failure.failed_qty - failure.resolved_qty == 125


@pytest.mark.asyncio
async def test_duplicate_po_number_raises_domain_error() -> None:
    class Result:
        def scalar_one_or_none(self) -> object:
            return object()

    class FakeDB:
        async def execute(self, *_: object) -> Result:
            return Result()

    payload = SimpleNamespace(po_number="PO-DUP")
    with pytest.raises(DomainError, match="PO number already exists"):
        await create_purchase_order(FakeDB(), payload, created_by=None)  # type: ignore[arg-type]


def test_stage_progress_api_returns_validation_error_for_bad_quantities() -> None:
    async def fake_db() -> object:
        yield SimpleNamespace()

    async def fake_user() -> object:
        return SimpleNamespace(id="user-id", role="owner")

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = fake_user
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/stage-progress",
            json={
                "purchase_order_id": "11111111-1111-1111-1111-111111111111",
                "stage": "cutting",
                "entry_date": "2026-05-04",
                "completed_today": 100,
                "approved_today": 80,
                "rejected_today": 40,
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_dispatch_api_requires_cost_fields() -> None:
    async def fake_db() -> object:
        yield SimpleNamespace()

    async def fake_user() -> object:
        return SimpleNamespace(id="user-id", role="manager")

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = fake_user
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/dispatch",
            json={
                "purchase_order_id": "11111111-1111-1111-1111-111111111111",
                "load_number": "L1",
                "shipped_qty": 100,
                "cost_type": "invoice_percent",
                "shipped_at": "2026-05-04",
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
