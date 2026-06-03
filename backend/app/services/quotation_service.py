from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.purchase_order import PurchaseOrder
from app.schemas.quotation import POQuotationRead, QuotationLineRead
from app.services.exceptions import DomainError
from app.services.operational_backfill import ensure_po_operational_data
from app.services.pdf_reports.report_renderer import render_report_pdf
from app.services.pdf_reports.report_schemas import ReportPayload


QUOTATION_TERMS = [
    "Prices are based on the PO quantity and recorded PO price.",
    "Dispatch date follows the promised dispatch date in the PO.",
    "Taxes/GST are shown only when configured in the PO system.",
    "Final billing should be verified against the approved buyer terms before shipment.",
]


async def build_po_quotation(db: AsyncSession, po_number: str) -> POQuotationRead:
    po = await _find_po(db, po_number)
    if po is None:
        raise DomainError(status_code=404, detail=f"PO {po_number!r} not found")
    await ensure_po_operational_data(db, po)

    product_name = po.product.product_name if po.product else "Product"
    product_category = po.product.product_category if po.product else "Not recorded"
    unit_price = po.selling_price or po.mrp
    subtotal = (Decimal(po.order_quantity_pcs) * unit_price).quantize(Decimal("0.01")) if unit_price is not None else None
    # There is no GST/tax field in the current schema. Keep this explicit so we
    # do not invent commercial terms in a customer-facing quotation.
    tax_rate = None
    tax_amount = None
    total = subtotal

    missing = []
    buyer_name = None
    if buyer_name is None:
        missing.append("buyer_name")
    if unit_price is None:
        missing.append("unit_price")
    missing.append("tax_rate")

    description = " | ".join(part for part in [product_name, po.design_code_snapshot, po.design_name_snapshot] if part)
    line = QuotationLineRead(
        description=description,
        quantity_pcs=int(po.order_quantity_pcs),
        unit_price=unit_price,
        amount=subtotal,
    )
    return POQuotationRead(
        po_number=po.po_number,
        buyer_name=buyer_name,
        product=product_name,
        product_category=product_category,
        design_code=po.design_code_snapshot,
        quantity_pcs=int(po.order_quantity_pcs),
        unit_price=unit_price,
        subtotal=subtotal,
        tax_rate_percent=tax_rate,
        tax_amount=tax_amount,
        total_amount=total,
        dispatch_date=po.promise_delivery_date,
        missing_fields=missing,
        terms=QUOTATION_TERMS,
        lines=[line],
    )


async def generate_po_quotation_pdf(db: AsyncSession, po_number: str, *, output_dir: Path | None = None) -> tuple[POQuotationRead, Path]:
    quotation = await build_po_quotation(db, po_number)
    output_dir = output_dir or (Path(__file__).resolve().parents[2] / "generated_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_po = "".join(ch if ch.isalnum() or ch in {"-", "_", "#"} else "_" for ch in quotation.po_number)
    output_path = output_dir / f"quotation_{safe_po}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    render_report_pdf(
        output_path,
        ReportPayload(
            title=f"Quotation - {quotation.po_number}",
            summary={
                "po_number": quotation.po_number,
                "buyer_name": quotation.buyer_name or "Not recorded",
                "dispatch_date": quotation.dispatch_date.isoformat(),
                "subtotal": str(quotation.subtotal) if quotation.subtotal is not None else "Not recorded",
                "tax": "Not configured",
                "total": str(quotation.total_amount) if quotation.total_amount is not None else "Not recorded",
                "missing_fields": ", ".join(quotation.missing_fields) if quotation.missing_fields else "None",
            },
            rows=[
                {
                    "description": line.description,
                    "quantity_pcs": line.quantity_pcs,
                    "unit_price": str(line.unit_price) if line.unit_price is not None else "Not recorded",
                    "amount": str(line.amount) if line.amount is not None else "Not recorded",
                }
                for line in quotation.lines
            ],
            recommendations=quotation.terms,
        ),
        report_type="quotation",
        generated_by="owner",
        filters={"po_number": quotation.po_number},
    )
    return quotation, output_path


async def _find_po(db: AsyncSession, po_number: str) -> PurchaseOrder | None:
    ref = po_number.strip()
    if not ref:
        return None
    result = await db.execute(
        select(PurchaseOrder)
        .where(PurchaseOrder.po_number.ilike(f"%{ref}%"))
        .options(
            selectinload(PurchaseOrder.product),
            selectinload(PurchaseOrder.fabric_plan),
            selectinload(PurchaseOrder.stage_summaries),
            selectinload(PurchaseOrder.dispatch_loads),
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    return result.scalars().first()
