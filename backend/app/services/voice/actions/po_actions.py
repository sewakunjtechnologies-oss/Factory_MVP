"""Purchase-order tools for the voice assistant.

Phase 1: read-only, returns SAMPLE DATA so the Gemini round-trip + tool dispatch
can be validated end-to-end without a database. Phase 2 swaps the sample-data
provider for real SQLAlchemy queries against PurchaseOrder/FabricPlan.

Each tool function is registered via `@tool()` and its docstring + type hints
become the function declaration the model sees, so be precise with both.

IMPORTANT: Do NOT add `from __future__ import annotations` to tool modules.
google-genai's automatic function calling does not resolve PEP-563 stringified
annotations — it calls `isinstance(value, annotation)` directly and crashes when
the annotation is a string. Keep type hints as real type objects in this file.
"""

from sqlalchemy import func, select

from app.models.purchase_order import PurchaseOrder

from ..db_context import current_session
from ..tools import tool


_SAMPLE_PENDING_POS = [
    {
        "po_number": "PO-2026-0042",
        "product": "Double Bed Sheet — Floral",
        "quantity_pieces": 12000,
        "shipment_date": "2026-05-30",
        "blocker": "fabric_shortage",
        "shortage_meters": 250,
    },
    {
        "po_number": "PO-2026-0045",
        "product": "King Bed Sheet — Plain Beige",
        "quantity_pieces": 6000,
        "shipment_date": "2026-06-04",
        "blocker": "mill_order_pending",
        "shortage_meters": 1800,
    },
    {
        "po_number": "PO-2026-0048",
        "product": "Single Bed Sheet — Stripes",
        "quantity_pieces": 4000,
        "shipment_date": "2026-05-22",
        "blocker": "qc_failed_batch",
        "shortage_meters": 0,
    },
]


@tool()
def list_pending_purchase_orders(blocker: str = "all") -> dict:
    """List purchase orders that need owner attention.

    Args:
        blocker: Filter by reason the PO is stuck. One of: "all", "fabric_shortage",
            "mill_order_pending", "qc_failed_batch". Default "all".

    Returns:
        A dict with `count` and `pending_pos` (list of PO summaries: po_number,
        product, quantity_pieces, shipment_date, blocker, shortage_meters).
    """
    if blocker == "all":
        rows = list(_SAMPLE_PENDING_POS)
    else:
        rows = [row for row in _SAMPLE_PENDING_POS if row["blocker"] == blocker]
    return {"count": len(rows), "pending_pos": rows}


@tool(requires_confirmation=True)
async def update_po_notes(po_number: str, note: str, confirmed: bool = False) -> dict:
    """Append a note (free-text) to an existing purchase order. Use this when the
    owner wants to record something about a PO — a reason for a delay, a special
    instruction, a remark about quality, etc.

    CONFIRMATION REQUIRED: first call with confirmed=False to preview what
    would change. After the owner says yes, call again with confirmed=True.

    Args:
        po_number: The PO number to attach the note to, e.g. "PO-2026-0042".
        note: The text to append. The note is added on a new line at the bottom
            of any existing notes; previous notes are preserved.
        confirmed: Owner has explicitly approved this write. Default False
            returns a preview without changing the database.

    Returns:
        A dict. When confirmed=False: {requires_confirmation, preview, po_number,
        note_to_append, current_notes}. When confirmed=True: {done: True,
        po_number, notes}. If the PO doesn't exist: {found: False, po_number}.
    """
    session = current_session()
    note = note.strip()
    if not note:
        return {"error": "note must not be empty", "po_number": po_number}

    result = await session.execute(
        select(PurchaseOrder).where(func.lower(PurchaseOrder.po_number) == po_number.lower())
    )
    po = result.scalar_one_or_none()
    if po is None:
        return {"found": False, "po_number": po_number}

    existing = (po.notes or "").rstrip()
    new_notes = f"{existing}\n{note}".strip() if existing else note

    if not confirmed:
        return {
            "requires_confirmation": True,
            "preview": f"Append this note to {po.po_number}: '{note}'.",
            "po_number": po.po_number,
            "note_to_append": note,
            "current_notes": po.notes,
        }

    po.notes = new_notes
    await session.commit()
    return {"done": True, "po_number": po.po_number, "notes": new_notes}


@tool()
def get_po_status(po_number: str) -> dict:
    """Look up a single purchase order by its PO number. Use this whenever the
    owner asks about a specific PO — its current blocker, what is stopping it,
    its shipment date, its product, its quantity, or its fabric situation.

    Args:
        po_number: The PO number to look up, e.g. "PO-2026-0042".

    Returns:
        A dict with the PO's product, quantity_pieces, shipment_date, blocker,
        and shortage_meters, or `{"found": False}` if no PO with that number
        is known.
    """
    for row in _SAMPLE_PENDING_POS:
        if row["po_number"].lower() == po_number.lower():
            return {"found": True, **row}
    return {"found": False, "po_number": po_number}
