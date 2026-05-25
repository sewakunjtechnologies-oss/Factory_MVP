"""Fabric stock tool — Phase 2, real DB.

IMPORTANT: do NOT add `from __future__ import annotations` here. The Gemini SDK
walks `func.__annotations__` and calls isinstance() on the annotation values,
which crashes when PEP-563 has stringified them.
"""

from decimal import Decimal

from sqlalchemy import func, select

from app.models.fabric import FabricInventory

from ..db_context import current_session
from ..tools import tool


def _decimal_to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


@tool()
async def get_fabric_stock(
    fabric_type: str = "",
    color: str = "",
    gsm: float = 0.0,
) -> dict:
    """Look up current fabric inventory in the factory.

    Use this whenever the owner asks how much fabric is left, available, in
    stock, or remaining — overall or for a specific fabric. The owner may
    speak naturally ("how much cotton is left?", "do we have any 150 GSM
    fabric?", "what's the white fabric situation?") — pass whatever they
    specified and leave the other args blank.

    Args:
        fabric_type: Optional fabric type filter (e.g. "cotton", "polyester").
            Empty string means no filter on type.
        color: Optional color filter (e.g. "white", "navy"). Empty string
            means no filter on color.
        gsm: Optional GSM weight filter. 0.0 means no filter.

    Returns:
        A dict with:
        - `total_meters`: sum of available_length_m across matching rows.
        - `lots`: list of matching inventory rows
          (fabric_type, color, gsm, width, available_length_m).
        - `match_count`: number of inventory rows matched.
        - `filters_applied`: which filters were used.
    """
    session = current_session()
    stmt = select(FabricInventory)
    filters_applied: dict = {}
    if fabric_type.strip():
        stmt = stmt.where(func.lower(FabricInventory.fabric_type) == fabric_type.strip().lower())
        filters_applied["fabric_type"] = fabric_type.strip()
    if color.strip():
        stmt = stmt.where(func.lower(FabricInventory.color) == color.strip().lower())
        filters_applied["color"] = color.strip()
    if gsm > 0:
        stmt = stmt.where(FabricInventory.gsm == Decimal(str(gsm)))
        filters_applied["gsm"] = gsm
    stmt = stmt.order_by(FabricInventory.fabric_type, FabricInventory.color)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    lots = [
        {
            "fabric_type": row.fabric_type,
            "color": row.color,
            "gsm": _decimal_to_float(row.gsm),
            "width": _decimal_to_float(row.width),
            "available_length_m": _decimal_to_float(row.available_length_m),
        }
        for row in rows
    ]
    total = sum(lot["available_length_m"] for lot in lots)
    return {
        "total_meters": round(total, 3),
        "match_count": len(lots),
        "filters_applied": filters_applied,
        "lots": lots,
    }
