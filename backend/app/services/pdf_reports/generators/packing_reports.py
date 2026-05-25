from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.purchase_order import PurchaseOrder
from app.models.stage import PackingOutput
from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators import format_date
from app.services.pdf_reports.report_schemas import ReportPayload


async def generate_packing_risk_report(access: FactoryAIDataAccess, filters: dict[str, Any]) -> ReportPayload:
    rows = []
    output_stmt = (
        select(PackingOutput, PurchaseOrder)
        .join(PurchaseOrder, PurchaseOrder.id == PackingOutput.purchase_order_id)
        .order_by(PackingOutput.output_date.desc())
    )
    output_rows = await access.db.execute(output_stmt)
    for output, po in output_rows.all():
        risk = output.required_workers > output.worker_count
        if not risk and not output.blocker_reason:
            continue
        rows.append(
            {
                "po_number": po.po_number,
                "date": format_date(output.output_date),
                "worker_count": output.worker_count,
                "required_workers": float(output.required_workers),
                "packed_qty": output.packed_qty,
                "pending_qty": output.pending_qty,
                "blocker_reason": output.blocker_reason or "-",
                "status": "risk" if risk else "blocked",
            }
        )

    return ReportPayload(
        title="Packing Risk Report",
        summary={"risk_rows": len(rows)},
        rows=rows,
        recommendations=["Increase packing workforce or rebalance dispatch priorities."],
    )
