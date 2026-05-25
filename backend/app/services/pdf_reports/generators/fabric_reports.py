from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.fabric import FabricInventory
from app.models.purchase_order import PurchaseOrder
from app.services.pdf_reports.data_access import FactoryAIDataAccess, decimal_to_float
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_fabric_shortage_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    po_filter = str(filters.get("po_number") or "").strip().upper()
    po_prefix = str(filters.get("po_prefix") or "").strip().upper()
    rows = []
    shortage_plans = await access.get_shortage_plans()
    for po, plan in shortage_plans:
        if po_filter and po.po_number.upper() != po_filter:
            continue
        if po_prefix and not po.po_number.upper().startswith(po_prefix):
            continue
        mill_req = await access.get_mill_requirement(po.id)
        rows.append(
            {
                "po_number": po.po_number,
                "product": po.product.product_name if po.product else "Product",
                "required_meters": decimal_to_float(plan.total_required_m),
                "available_meters": decimal_to_float(plan.available_m),
                "shortage_meters": decimal_to_float(plan.shortage_m),
                "mill_order_requirement_status": mill_req.status.value if mill_req else "not_created",
            }
        )
    return ReportPayload(
        title="Fabric Shortage Report",
        summary={"shortage_pos": len(rows)},
        rows=rows,
        recommendations=["Create or follow up mill orders for every open shortage."],
    )


async def generate_fabric_stock_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    result = await access.db.execute(select(FabricInventory).order_by(FabricInventory.fabric_type.asc(), FabricInventory.color.asc()))
    rows = []
    for item in result.scalars().all():
        rows.append(
            {
                "fabric_type": item.fabric_type,
                "color": item.color,
                "gsm": decimal_to_float(item.gsm),
                "width": decimal_to_float(item.width),
                "available_meters": decimal_to_float(item.available_length_m),
                "approximate_rolls": item.approximate_rolls if item.approximate_rolls is not None else "-",
            }
        )
    return ReportPayload(
        title="Fabric Stock Summary",
        summary={"stock_rows": len(rows)},
        rows=rows,
        recommendations=["Reconcile fabric stock with PO-wise requirement daily."],
    )


async def generate_fabric_verification_pending_report(access: FactoryAIDataAccess, _: dict[str, Any]) -> ReportPayload:
    rows = []
    po_result = await access.db.execute(select(PurchaseOrder.id, PurchaseOrder.po_number))
    po_map = {str(po_id): po_number for po_id, po_number in po_result.all()}
    pending = await access.get_fabric_verification_pending()
    for receipt in pending:
        rows.append(
            {
                "receipt_id": str(receipt.id),
                "po_number": po_map.get(str(receipt.purchase_order_id), "-") if receipt.purchase_order_id else "-",
                "supplier": receipt.supplier_name,
                "fabric_type": receipt.fabric_type,
                "color": receipt.color,
                "received_meters": decimal_to_float(receipt.received_meters or receipt.received_length_m),
                "received_at": format_date(receipt.received_at),
                "status": receipt.verification_status.value,
            }
        )
    return ReportPayload(
        title="Pending Fabric Verification Report",
        summary={"pending_receipts": len(rows)},
        rows=rows,
        recommendations=["Complete verification before issuing fabric to cutting."],
    )
