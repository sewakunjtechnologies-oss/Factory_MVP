"""Voice/text assistant endpoints.

POST /api/v1/voice/ask  — typed question or transcribed-speech question. Runs
Gemini brain with the tool catalog (PDF generation, fabric/PO/dispatch lookups,
PO feasibility, etc.) and returns the text answer plus any artifacts the tools
produced (e.g. a generated PDF's download URL).

Errors from Gemini (rate limits, model overloads, auth) are translated to clean
HTTP responses so the frontend can show a useful toast instead of a generic
"Network error".
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors as genai_errors
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_owner_or_manager
from app.models.dispatch import DispatchLoad
from app.models.fabric import FabricMillOrder
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services.voice import artifacts_scope, ask_async, use_session
from app.services.voice.factory_queries import answer_factory_question

logger = logging.getLogger(__name__)
router = APIRouter()


class VoiceAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class VoiceArtifact(BaseModel):
    type: str
    title: str | None = None
    download_url: str | None = None
    report_type: str | None = None
    report_id: str | None = None


class VoiceAskResponse(BaseModel):
    answer: str
    artifacts: List[VoiceArtifact] = Field(default_factory=list)


_GEMINI_USER_MESSAGES = {
    401: "The assistant is misconfigured (Gemini auth). Check the GEMINI_API_KEY env var.",
    403: "Gemini refused the request — check API quota and key permissions.",
    429: "The assistant is rate-limited right now. Please try again in a few seconds.",
    500: "Gemini is temporarily unavailable. Please try again.",
    502: "Gemini is temporarily unavailable. Please try again.",
    503: "The assistant is busy right now (model overloaded). Please try again in a few seconds.",
    504: "Gemini timed out. Please try again.",
}


@router.post("/ask", response_model=VoiceAskResponse)
async def ask_voice_assistant(
    payload: VoiceAskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> VoiceAskResponse:
    try:
        with use_session(db):
            with artifacts_scope() as sink:
                direct = await answer_factory_question(db, payload.message)
                answer = direct.answer if direct is not None else await ask_async(await _build_grounded_gemini_prompt(db, payload.message))
                artifacts = list(sink)
    except genai_errors.APIError as error:
        # Covers ClientError (4xx) + ServerError (5xx) + any future subclass.
        code = getattr(error, "code", 502) or 502
        # Map to a 502 so the frontend treats this as a service-availability
        # problem (retryable) rather than a request error. We pass the
        # user-friendly message through to the UI.
        detail = _GEMINI_USER_MESSAGES.get(code, "The assistant could not respond. Please try again.")
        logger.warning("voice/ask: Gemini returned %s — %s", code, error)
        raise HTTPException(status_code=502, detail=detail) from error
    except Exception as error:  # noqa: BLE001
        logger.exception("voice/ask: unexpected failure")
        raise HTTPException(status_code=500, detail="The assistant hit an unexpected error.") from error
    return VoiceAskResponse(
        answer=answer,
        artifacts=[VoiceArtifact.model_validate(item) for item in artifacts],
    )


async def _build_grounded_gemini_prompt(db: AsyncSession, owner_message: str) -> str:
    """Attach a compact live DB snapshot so Gemini answers from factory data.

    The tool catalog can still be used by Gemini for detailed lookups and PDFs,
    but this context keeps broad/natural questions grounded instead of generic.
    """
    po_result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.product), selectinload(PurchaseOrder.fabric_plan), selectinload(PurchaseOrder.dispatch_loads))
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.po_number.asc())
        .limit(45)
    )
    pos = list(po_result.scalars().all())

    line_result = await db.execute(
        select(ProductFabricLine, Product)
        .join(Product, Product.id == ProductFabricLine.product_id)
        .order_by(Product.product_name.asc(), ProductFabricLine.fabric_code.asc())
        .limit(60)
    )
    fabric_lines = line_result.all()

    mill_result = await db.execute(
        select(FabricMillOrder, PurchaseOrder)
        .join(PurchaseOrder, PurchaseOrder.id == FabricMillOrder.purchase_order_id)
        .order_by(FabricMillOrder.committed_delivery_date.asc())
        .limit(30)
    )
    mill_orders = mill_result.all()

    vehicle_result = await db.execute(select(Vehicle).where(Vehicle.is_active.is_(True)).order_by(Vehicle.cbm_capacity.asc()))
    vehicles = list(vehicle_result.scalars().all())

    dispatch_result = await db.execute(
        select(DispatchLoad, PurchaseOrder)
        .join(PurchaseOrder, PurchaseOrder.id == DispatchLoad.purchase_order_id)
        .order_by(DispatchLoad.shipped_at.desc())
        .limit(25)
    )
    dispatch_loads = dispatch_result.all()

    po_lines = []
    for po in pos:
        product = po.product
        plan = po.fabric_plan
        shipped = sum(int(load.shipped_qty or 0) for load in po.dispatch_loads)
        po_lines.append(
            "- "
            f"{po.po_number}: product={product.product_name if product else 'unknown'}, "
            f"qty={po.order_quantity_pcs}, status={po.status.value}, "
            f"order_date={po.order_date}, deadline={po.promise_delivery_date}, "
            f"fabric_required_m={plan.total_required_m if plan else 'not_planned'}, "
            f"fabric_shortage_m={plan.shortage_m if plan else 'unknown'}, "
            f"shipped_pcs={shipped}, notes={(po.notes or '')[:120]}"
        )

    fabric_context = []
    for line, product in fabric_lines:
        fabric_context.append(
            "- "
            f"category={product.product_name}, fabric={line.fabric_code}, "
            f"pieces_in_stock={line.pieces_in_stock}, pieces_short={line.pieces_short}, "
            f"stock_meters={line.stock_meters}, stock_status={line.stock_status}, "
            f"cutting={line.cutting}, stitching={line.stitching}, packing={line.packing}, dispatch={line.dispatch}"
        )

    mill_context = []
    for order, po in mill_orders:
        mill_context.append(
            "- "
            f"{order.mill_name} for {po.po_number}: ordered_meters={order.ordered_meters}, "
            f"status={order.status.value}, committed_delivery_date={order.committed_delivery_date}, "
            f"actual_delivery_date={order.actual_delivery_date}, invoice={order.invoice_number or 'not_set'}"
        )

    vehicle_context = [
        f"- {vehicle.name}: cbm={vehicle.cbm_capacity}, max_weight_kg={vehicle.max_weight_kg}"
        for vehicle in vehicles
    ]

    dispatch_context = []
    for load, po in dispatch_loads:
        dispatch_context.append(
            "- "
            f"{load.load_number} / {po.po_number}: shipped={load.shipped_qty}, vehicle={load.vehicle_type or 'not_set'}, "
            f"date={load.shipped_at}, shortfall={load.shortfall_qty}, cost={load.dispatch_cost}"
        )

    return f"""
The owner asked: {owner_message}

Use this live database context first. If exact detail is missing, use the available voice tools. Do not invent records.
Answer in a short factory-owner style. If the owner asks to update/create/mark/order/receive/move anything, ask for confirmation before writing unless the system tool has already returned a preview.

Current PO snapshot:
{chr(10).join(po_lines) or "- No POs found."}

Product fabric and pieces snapshot:
{chr(10).join(fabric_context) or "- No product fabric lines found."}

Mill orders / invoices:
{chr(10).join(mill_context) or "- No mill orders found."}

Truck load planner vehicle lengths:
{chr(10).join(vehicle_context) or "- No vehicles found."}

Recent dispatch loads:
{chr(10).join(dispatch_context) or "- No dispatch loads found."}
""".strip()
