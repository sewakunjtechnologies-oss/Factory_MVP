from __future__ import annotations

from datetime import date
from math import ceil


def safe_percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def completion_percentage(order_qty: int, shipped_qty: int, latest_stage_approved: int = 0) -> float:
    shipped_based = safe_percent(float(shipped_qty), float(order_qty))
    stage_based = safe_percent(float(latest_stage_approved), float(order_qty))
    return max(shipped_based, stage_based)


def stage_progress_percentage(input_qty: int, approved_qty: int) -> float:
    return safe_percent(float(approved_qty), float(input_qty))


def delayed_days(expected_date: date | None, today: date | None = None) -> int:
    if expected_date is None:
        return 0
    now = today or date.today()
    return max((now - expected_date).days, 0)


def shipment_risk(promise_date: date | None, pending_qty: int, today: date | None = None) -> bool:
    if promise_date is None or pending_qty <= 0:
        return False
    now = today or date.today()
    return (promise_date - now).days <= 2


def expected_completion_date(
    pending_qty: int,
    daily_output_estimate: int,
    start_date: date | None = None,
) -> date | None:
    if pending_qty <= 0:
        return start_date or date.today()
    if daily_output_estimate <= 0:
        return None
    days = ceil(pending_qty / daily_output_estimate)
    return (start_date or date.today()).fromordinal((start_date or date.today()).toordinal() + days)


def fabric_shortage_meters(required: float, available: float) -> float:
    return round(max(required - available, 0.0), 3)


def dispatch_readiness(packing_approved: int, shipped_qty: int) -> int:
    return max(packing_approved - shipped_qty, 0)


def packing_risk(required_workers: float, actual_workers: float) -> bool:
    return required_workers > actual_workers


def contractor_delay_score(pending_qty: int, delay_days_value: int) -> float:
    return round((pending_qty * 0.01) + (delay_days_value * 4), 2)


def urgent_priority_score(
    pending_qty: int,
    delay_days_value: int,
    shortage_m: float,
    days_to_deadline: int | None,
) -> float:
    deadline_risk = 0
    if days_to_deadline is not None:
        deadline_risk = 15 if days_to_deadline <= 1 else 8 if days_to_deadline <= 3 else 0
    return round(
        (pending_qty * 0.005)
        + (delay_days_value * 3)
        + (shortage_m * 0.02)
        + deadline_risk,
        2,
    )

