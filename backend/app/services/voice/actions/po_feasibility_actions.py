"""PO fabric feasibility tool — read-only.

Given either an existing PO number or a candidate spec (fabric_type/color/gsm/
width + quantity + per-piece usage + wastage), this tool calculates how much
fabric is required, looks up matching inventory, and returns whether the order
can run from stock or how short it is.

IMPORTANT: do NOT add ``from __future__ import annotations`` — Gemini's
automatic function calling cannot resolve PEP-563 stringified annotations.
"""

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.fabric import FabricInventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.services.fabric_planning import calculate_fabric_plan

from ..db_context import current_session
from ..tools import tool


def _to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def _matching_inventory(session, fabric_type: str, color: str, gsm: Decimal, width: Decimal) -> list[FabricInventory]:
    stmt = select(FabricInventory).where(
        func.lower(FabricInventory.fabric_type) == fabric_type.lower(),
        func.lower(FabricInventory.color) == color.lower(),
        FabricInventory.gsm == gsm,
        FabricInventory.width == width,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _verdict(shortage_m: Decimal) -> str:
    if shortage_m <= Decimal("0"):
        return "ready"
    return "shortage"


@tool()
async def check_po_feasibility(
    po_number: str = "",
    quantity_pieces: int = 0,
    fabric_type: str = "",
    color: str = "",
    gsm: float = 0.0,
    width: float = 0.0,
    per_piece_fabric_usage_m: float = 0.0,
    wastage_percent: float = 5.0,
) -> dict:
    """Check whether the factory has enough fabric to run a PO.

    Two modes:
    1) Existing PO — pass only ``po_number`` (e.g. "PO-2026-0042"). The tool
       reads the PO's product, computes required fabric and compares against
       matching inventory.
    2) Hypothetical PO — leave ``po_number`` empty and pass the spec:
       ``quantity_pieces``, ``fabric_type``, ``color``, ``gsm``, ``width``,
       ``per_piece_fabric_usage_m`` (meters per piece, e.g. 4.5 for a double
       bed sheet), ``wastage_percent`` (default 5%).

    Use this whenever the owner asks "do I have enough fabric for…" or
    "can we run X pieces of…" or before creating a PO. After this returns,
    if ``verdict == "shortage"`` you should offer to either place a mill
    order (use ``place_mill_order``) or generate a fabric shortage PDF.

    Returns:
        Dict with:
        - `mode`: "existing_po" or "hypothetical".
        - `po_number`: echoed when mode=existing_po.
        - `product_summary`: human-readable line (mode=existing_po).
        - `quantity_pieces`: order qty.
        - `fabric_spec`: {fabric_type, color, gsm, width}.
        - `required_m`: meters needed (excludes wastage).
        - `wastage_m`: wastage allowance.
        - `total_required_m`: required + wastage.
        - `available_m`: meters in stock matching the spec.
        - `shortage_m`: max(0, total_required - available).
        - `verdict`: "ready" (no shortage) or "shortage".
        - `lots`: matching inventory lots (fabric_type/color/gsm/width/available_length_m).
        - `error`: None on success, else a short message.
    """
    session = current_session()

    # Mode 1: existing PO
    if po_number.strip():
        stmt = (
            select(PurchaseOrder)
            .where(func.upper(PurchaseOrder.po_number) == po_number.strip().upper())
            .options(selectinload(PurchaseOrder.product))
        )
        result = await session.execute(stmt)
        po = result.scalar_one_or_none()
        if po is None:
            return {
                "mode": "existing_po",
                "po_number": po_number,
                "verdict": "unknown",
                "error": f"PO {po_number!r} not found.",
            }
        product: Product | None = getattr(po, "product", None)
        if product is None:
            return {
                "mode": "existing_po",
                "po_number": po.po_number,
                "verdict": "unknown",
                "error": "PO has no product attached.",
            }
        plan = calculate_fabric_plan(
            order_qty_pcs=int(po.order_quantity_pcs),
            per_piece_fabric_usage_m=product.per_piece_fabric_usage_m,
            wastage_percent=product.wastage_percent,
            roll_length_m=product.roll_length_m,
        )
        lots = await _matching_inventory(session, product.fabric_type, product.color, product.gsm, product.width)
        available = sum((row.available_length_m for row in lots), Decimal("0"))
        shortage = max(Decimal("0"), plan["total_required_m"] - available)
        return {
            "mode": "existing_po",
            "po_number": po.po_number,
            "product_summary": f"{product.product_name} ({product.fabric_type}, {product.color}, {_to_float(product.gsm)} GSM)",
            "quantity_pieces": int(po.order_quantity_pcs),
            "fabric_spec": {
                "fabric_type": product.fabric_type,
                "color": product.color,
                "gsm": _to_float(product.gsm),
                "width": _to_float(product.width),
            },
            "required_m": float(plan["required_m"]),
            "wastage_m": float(plan["wastage_m"]),
            "total_required_m": float(plan["total_required_m"]),
            "available_m": float(available),
            "shortage_m": float(shortage),
            "verdict": _verdict(shortage),
            "lots": [
                {
                    "fabric_type": lot.fabric_type,
                    "color": lot.color,
                    "gsm": _to_float(lot.gsm),
                    "width": _to_float(lot.width),
                    "available_length_m": _to_float(lot.available_length_m),
                }
                for lot in lots
            ],
            "error": None,
        }

    # Mode 2: hypothetical spec
    if quantity_pieces <= 0 or not fabric_type.strip() or per_piece_fabric_usage_m <= 0:
        return {
            "mode": "hypothetical",
            "verdict": "unknown",
            "error": "Need at least quantity_pieces, fabric_type and per_piece_fabric_usage_m to estimate feasibility.",
        }
    try:
        plan = calculate_fabric_plan(
            order_qty_pcs=quantity_pieces,
            per_piece_fabric_usage_m=_decimal(per_piece_fabric_usage_m),
            wastage_percent=_decimal(wastage_percent),
        )
    except (InvalidOperation, ValueError) as exc:
        return {
            "mode": "hypothetical",
            "verdict": "unknown",
            "error": f"Could not compute fabric plan: {exc}",
        }

    lots: list[FabricInventory] = []
    if color.strip() and gsm > 0 and width > 0:
        lots = await _matching_inventory(session, fabric_type, color, _decimal(gsm), _decimal(width))
    available = sum((row.available_length_m for row in lots), Decimal("0"))
    shortage = max(Decimal("0"), plan["total_required_m"] - available)
    return {
        "mode": "hypothetical",
        "quantity_pieces": quantity_pieces,
        "fabric_spec": {
            "fabric_type": fabric_type,
            "color": color or None,
            "gsm": gsm or None,
            "width": width or None,
        },
        "required_m": float(plan["required_m"]),
        "wastage_m": float(plan["wastage_m"]),
        "total_required_m": float(plan["total_required_m"]),
        "available_m": float(available),
        "shortage_m": float(shortage),
        "verdict": _verdict(shortage),
        "lots": [
            {
                "fabric_type": lot.fabric_type,
                "color": lot.color,
                "gsm": _to_float(lot.gsm),
                "width": _to_float(lot.width),
                "available_length_m": _to_float(lot.available_length_m),
            }
            for lot in lots
        ],
        "error": None,
    }
