"""Dispatch tool — Phase 2, real DB.

IMPORTANT: no `from __future__ import annotations` (breaks Gemini auto FC).
"""

from datetime import date as _date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.dispatch import DispatchLoad
from app.models.purchase_order import PurchaseOrder

from ..db_context import current_session
from ..tools import tool


def _to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


@tool()
async def list_todays_dispatches() -> dict:
    """List every dispatch load shipped today, along with which PO each one
    belongs to.

    Use this whenever the owner asks about today's dispatches, deliveries,
    shipments, or trucks that went out today. Do not call this for past or
    future dates — only today.

    Returns:
        A dict with:
        - `date`: today's date in ISO format (YYYY-MM-DD).
        - `count`: number of dispatch loads shipped today.
        - `total_pieces_shipped`: sum of shipped_qty across today's loads.
        - `loads`: list of load summaries with load_number, po_number,
          shipped_qty, vehicle_identifier, transporter_name, destination,
          dispatch_cost.
    """
    session = current_session()
    today = _date.today()
    stmt = (
        select(DispatchLoad)
        .where(DispatchLoad.shipped_at == today)
        .options(selectinload(DispatchLoad.purchase_order))
        .order_by(DispatchLoad.load_number)
    )
    result = await session.execute(stmt)
    loads = list(result.scalars().all())

    items = []
    total_pieces = 0
    for load in loads:
        po: PurchaseOrder | None = getattr(load, "purchase_order", None)
        items.append(
            {
                "load_number": load.load_number,
                "po_number": po.po_number if po else None,
                "shipped_qty": int(load.shipped_qty),
                "vehicle_identifier": load.vehicle_identifier,
                "transporter_name": load.transporter_name,
                "destination": load.destination,
                "dispatch_cost": _to_float(load.dispatch_cost),
            }
        )
        total_pieces += int(load.shipped_qty)
    return {
        "date": today.isoformat(),
        "count": len(items),
        "total_pieces_shipped": total_pieces,
        "loads": items,
    }
