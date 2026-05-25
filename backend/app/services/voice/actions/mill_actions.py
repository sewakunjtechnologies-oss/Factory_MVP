"""Mill-order write tool — Phase 2 follow-up.

IMPORTANT: no `from __future__ import annotations` (breaks Gemini auto FC).
"""

from datetime import date as _date
from decimal import Decimal

from sqlalchemy import func, select

from app.models.fabric import FabricMillOrder
from app.models.enums import FabricMillOrderStatus
from app.models.purchase_order import PurchaseOrder

from ..db_context import current_session
from ..tools import tool


@tool(requires_confirmation=True)
async def place_mill_order(
    po_number: str,
    mill_name: str,
    meters: float,
    committed_delivery_date_iso: str,
    confirmed: bool = False,
) -> dict:
    """Place a fabric order with a mill, linked to an existing purchase order.
    Use this whenever the owner says they want to order fabric, place an order
    with a mill, or solve a fabric shortage for a specific PO.

    CONFIRMATION REQUIRED: first call with confirmed=False to preview the order.
    After the owner says yes, call again with confirmed=True.

    Args:
        po_number: The PO that needs the fabric, e.g. "PO-2026-0042".
        mill_name: Plain-text name of the mill (e.g. "Sharma Mills"). The mill
            does NOT need to already exist as a contractor — we just store the name.
        meters: Number of meters to order. Must be > 0.
        committed_delivery_date_iso: Mill's promised delivery date in ISO format
            "YYYY-MM-DD". If the owner says "next Friday" or similar, convert it
            yourself before calling.
        confirmed: Owner has explicitly approved. Default False returns a preview.

    Returns:
        A dict. When confirmed=False: {requires_confirmation, preview, po_number,
        mill_name, meters, committed_delivery_date}. When confirmed=True:
        {done: True, mill_order_id, po_number, mill_name, meters,
        committed_delivery_date, status}. If the PO doesn't exist or inputs are
        invalid: {error, ...}.
    """
    session = current_session()

    if meters <= 0:
        return {"error": "meters must be greater than zero", "meters": meters}
    if not mill_name.strip():
        return {"error": "mill_name must not be empty"}

    try:
        delivery_date = _date.fromisoformat(committed_delivery_date_iso)
    except ValueError:
        return {
            "error": "committed_delivery_date_iso must be in YYYY-MM-DD format",
            "value_received": committed_delivery_date_iso,
        }
    if delivery_date < _date.today():
        return {
            "error": "committed_delivery_date_iso cannot be in the past",
            "date_received": committed_delivery_date_iso,
            "today": _date.today().isoformat(),
        }

    po_result = await session.execute(
        select(PurchaseOrder).where(func.lower(PurchaseOrder.po_number) == po_number.lower())
    )
    po = po_result.scalar_one_or_none()
    if po is None:
        return {"found": False, "po_number": po_number}

    if not confirmed:
        return {
            "requires_confirmation": True,
            "preview": (
                f"Place a mill order with {mill_name.strip()} for {meters:g} meters "
                f"of fabric for {po.po_number}, delivery promised by {delivery_date.isoformat()}."
            ),
            "po_number": po.po_number,
            "mill_name": mill_name.strip(),
            "meters": meters,
            "committed_delivery_date": delivery_date.isoformat(),
        }

    order = FabricMillOrder(
        purchase_order_id=po.id,
        mill_name=mill_name.strip(),
        ordered_meters=Decimal(str(meters)),
        committed_delivery_date=delivery_date,
        status=FabricMillOrderStatus.ordered,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    return {
        "done": True,
        "mill_order_id": str(order.id),
        "po_number": po.po_number,
        "mill_name": order.mill_name,
        "meters": float(order.ordered_meters),
        "committed_delivery_date": order.committed_delivery_date.isoformat(),
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
    }
