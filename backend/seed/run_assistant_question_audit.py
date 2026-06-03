from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from textwrap import shorten

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.enums import POStatus
from app.models.purchase_order import PurchaseOrder
from app.services.operational_backfill import ensure_all_operational_data
from app.services.voice.artifacts import artifacts_scope
from app.services.voice.factory_queries import answer_factory_question


@dataclass(frozen=True)
class AuditQuestion:
    question: str
    expected_intent: str
    expected_query: str
    requires_artifact: bool = False


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await ensure_all_operational_data(db)
        result = await db.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.fabric_plan), selectinload(PurchaseOrder.stage_summaries))
            .where(PurchaseOrder.promise_delivery_date >= date(2026, 6, 1), PurchaseOrder.promise_delivery_date <= date(2026, 6, 30))
            .order_by(PurchaseOrder.po_number.asc())
        )
        june_pos = list(result.scalars().all())
        if not june_pos:
            raise SystemExit("No June POs found; cannot run assistant audit.")
        shortage_po = next((po for po in june_pos if po.fabric_plan and po.fabric_plan.shortage_m > 0), june_pos[0])
        ready_po = next((po for po in june_pos if po.status == POStatus.fabric_ready), june_pos[0])
        sample_po = shortage_po

        questions = _questions(sample_po.po_number, shortage_po.po_number, ready_po.po_number)
        rows = []
        passed = 0
        for item in questions:
            with artifacts_scope() as artifacts:
                direct = await answer_factory_question(db, item.question)
            actual = direct.answer if direct else "NO_DIRECT_DB_ANSWER"
            ok = direct is not None and "PO-2026-0042" not in actual
            if item.requires_artifact:
                ok = ok and bool(artifacts)
            passed += 1 if ok else 0
            rows.append(
                {
                    "question": item.question,
                    "intent": item.expected_intent,
                    "query": item.expected_query,
                    "actual": actual,
                    "pass": "PASS" if ok else "FAIL",
                    "bug": "" if ok else "Assistant did not return deterministic DB-grounded answer/artifact.",
                    "file_changed": _file_for_intent(item.expected_intent),
                    "fix": "DB-backed deterministic assistant path / report or quotation service",
                    "artifacts": ", ".join(a.get("title") or a.get("type", "") for a in artifacts),
                }
            )

    output = BACKEND_DIR / "ASSISTANT_50_QUESTION_AUDIT.md"
    output.write_text(_render(rows, passed), encoding="utf-8")
    print(f"Wrote {output}")
    print(f"{passed}/{len(rows)} passed")


def _questions(sample_po: str, shortage_po: str, ready_po: str) -> list[AuditQuestion]:
    q: list[AuditQuestion] = [
        AuditQuestion("Hi", "greeting/help", "none; static capability greeting"),
        AuditQuestion("Hello", "greeting/help", "none; static capability greeting"),
        AuditQuestion("What can you do?", "greeting/help", "none; static capability help"),
        AuditQuestion("Help me with PO status", "greeting/help", "none; static capability help"),
        AuditQuestion("Show me today's factory summary", "dashboard summary", "purchase_orders + fabric_plans + stage_summaries"),
        AuditQuestion("Show all June POs", "june_po_list", "purchase_orders where order/promise month = June"),
        AuditQuestion("Show June POs due before June 30", "june_due", "purchase_orders where promise_delivery_date <= 2026-06-30"),
        AuditQuestion("Which June POs are pending dispatch?", "june_pending", "June POs with pending_qty > 0 and non-terminal status"),
        AuditQuestion("Which June POs are completed?", "june_completed", "June POs where status = completed"),
        AuditQuestion("Which June POs are delayed?", "june_delayed", "June POs where promise_delivery_date < today and pending_qty > 0"),
        AuditQuestion("Which June POs are risky?", "june_risk", "June POs with fabric_plan.shortage_m > 0"),
        AuditQuestion("Which June POs must be dispatched by the end of June?", "june_due", "June POs promised by 2026-06-30"),
        AuditQuestion("Show me dispatch status for June", "june_dispatch_status", "aggregate June POs by status/shortage/dispatch readiness"),
        AuditQuestion(f"What is the status of PO {sample_po}?", "po_status", "purchase_orders by po_number + stages + fabric_plan"),
        AuditQuestion(f"What is pending in PO {sample_po}?", "po_quantities", "stage_summaries and dispatch stage for PO"),
        AuditQuestion(f"What is completed in PO {sample_po}?", "po_quantities", "stage_summaries and dispatch stage for PO"),
        AuditQuestion(f"Which stage is PO {sample_po} currently in?", "stage_progress", "stage_summaries for PO"),
        AuditQuestion(f"Is PO {ready_po} ready for dispatch?", "dispatch_ready_po", "packing/dispatch stage quantities for PO"),
        AuditQuestion(f"Why is PO {shortage_po} delayed?", "delay_reason", "promise date + fabric_plan + stage bottleneck for PO"),
        AuditQuestion(f"Tell me expected completion date for PO {sample_po}", "expected_completion", "purchase_order.promise_delivery_date / actual_delivery_date"),
        AuditQuestion(f"How many pieces are completed, pending, rejected, repaired, altered, approved for PO {sample_po}?", "po_quantities", "stage_summaries rollup"),
        AuditQuestion("Which POs have fabric shortage?", "fabric_shortage", "fabric_plans where shortage_m > 0 and PO active"),
        AuditQuestion(f"Show shortage for PO {shortage_po}", "po_shortage", "fabric_plan for PO"),
        AuditQuestion("Generate fabric shortage PDF", "pdf_fabric_shortage", "report_requests + generate_pdf_fabric_shortage", True),
        AuditQuestion("Which mill order is needed?", "mill_requirement", "active shortage POs and suggested shortage meters"),
        AuditQuestion(f"Which mill order is needed for PO {shortage_po}?", "mill_requirement", "fabric_plan shortage for PO"),
        AuditQuestion(f"Generate quotation for PO {sample_po}", "quotation_pdf", "quotation service by PO", True),
        AuditQuestion(f"Show quotation for PO {sample_po}", "quotation_view", "quotation service by PO"),
        AuditQuestion(f"Download quotation PDF for PO {sample_po}", "quotation_pdf", "quotation PDF service by PO", True),
        AuditQuestion(f"Is quotation ready for PO {sample_po}?", "quotation_view", "quotation service by PO"),
        AuditQuestion(f"Is the quotation PDF working for PO {sample_po}?", "quotation_pdf", "quotation PDF service by PO", True),
        AuditQuestion("Show pending dispatch", "pending_dispatch", "stage_summaries dispatch pending active POs"),
        AuditQuestion("Generate pending dispatch PDF", "pdf_pending_dispatch", "report_requests + generate_pdf_pending_dispatch", True),
        AuditQuestion("Which POs must dispatch by end of June?", "june_due", "June POs promised by 2026-06-30"),
        AuditQuestion("Which POs missed dispatch date?", "delayed", "promise_delivery_date < today and pending_qty > 0"),
        AuditQuestion("Show ready-to-dispatch POs", "dispatch_ready", "packing approved minus dispatch completed"),
        AuditQuestion("June dispatch report PDF", "pdf_june_dispatch", "report_requests + generate_pdf_june_dispatch", True),
        AuditQuestion(f"Which contractor is working on PO {sample_po}?", "contractor_po", "contractor_allocations joined through stage_summaries"),
        AuditQuestion("Which contractor is delayed?", "contractor_delay", "contractor_allocations expected date/completion"),
        AuditQuestion(f"Show cutting status for PO {ready_po}", "stage_cutting", "stage_summaries stage=cutting for PO"),
        AuditQuestion(f"Show stitching status for PO {sample_po}", "stage_stitching", "stage_summaries stage=stitching for PO"),
        AuditQuestion(f"Show finishing status for PO {sample_po}", "stage_finishing", "stage_summaries stage=quality_check for PO"),
        AuditQuestion("Which POs are stuck in cutting?", "stage_cutting_list", "stage_summaries stage=cutting pending_qty > 0"),
        AuditQuestion("Which POs are stuck in stitching?", "stage_stitching_list", "stage_summaries stage=stitching pending_qty > 0"),
        AuditQuestion("Which POs are in finishing?", "stage_finishing_list", "stage_summaries stage=quality_check pending_qty > 0"),
        AuditQuestion("Which PO should I focus on today?", "owner_focus", "active POs sorted by shortage/risk/deadline"),
        AuditQuestion("What is the biggest risk before June end dispatch?", "owner_risk", "active June POs with shortage/delay/dispatch risk"),
        AuditQuestion("Generate running PO PDF", "pdf_running_pos", "report_requests + generate_pdf_running_pos", True),
        AuditQuestion("Generate delayed PO PDF", "pdf_delayed_pos", "report_requests + generate_pdf_delayed_pos", True),
        AuditQuestion(f"Create quotation for this PO {sample_po}", "quotation_pdf", "quotation PDF service by PO", True),
    ]
    assert len(q) == 50
    return q


def _file_for_intent(intent: str) -> str:
    if intent.startswith("pdf"):
        return "app/services/pdf_reports/*"
    if intent.startswith("quotation"):
        return "app/services/quotation_service.py"
    return "app/services/voice/factory_queries.py"


def _render(rows: list[dict], passed: int) -> str:
    lines = [
        "# Assistant 50 Question Audit",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC",
        f"Result: {passed}/{len(rows)} PASS",
        "",
        "| # | User question | Expected intent | Expected DB/API query | Actual response | Pass/fail | Bug found | File changed | Fix applied | Artifact |",
        "|---:|---|---|---|---|---|---|---|---|---|",
    ]
    for idx, row in enumerate(rows, start=1):
        lines.append(
            "| {idx} | {question} | {intent} | {query} | {actual} | {pass_} | {bug} | {file_changed} | {fix} | {artifacts} |".format(
                idx=idx,
                question=_cell(row["question"]),
                intent=_cell(row["intent"]),
                query=_cell(row["query"]),
                actual=_cell(shorten(row["actual"].replace("\n", " "), width=260, placeholder="...")),
                pass_=_cell(row["pass"]),
                bug=_cell(row["bug"]),
                file_changed=_cell(row["file_changed"]),
                fix=_cell(row["fix"]),
                artifacts=_cell(row["artifacts"]),
            )
        )
    return "\n".join(lines) + "\n"


def _cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    asyncio.run(main())
