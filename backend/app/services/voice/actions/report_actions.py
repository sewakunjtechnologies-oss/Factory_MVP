"""PDF report generation tool for the voice assistant.

The brain can hand the owner a downloadable PDF for any report registered in
``app.services.pdf_reports.report_registry``. The tool runs the report
synchronously inside the same request session and returns a download URL the
chat/voice UI can render as a button.

IMPORTANT: do NOT add ``from __future__ import annotations`` here — the Gemini
SDK introspects ``func.__annotations__`` directly and breaks on stringified
hints.
"""

import json

from app.services.pdf_reports.report_registry import REPORT_REGISTRY
from app.services.pdf_reports.report_schemas import ReportGenerateRequest
from app.services.pdf_reports.report_service import ReportService

from ..artifacts import add_artifact
from ..db_context import current_session
from ..tools import tool


# Curated mapping from natural-language report names → registry keys. Lets the
# model pick the right report when the owner asks in plain English. Keep keys
# all-lowercase; lookup is case-insensitive.
_NL_ALIASES = {
    "daily summary": "generate_pdf_daily_factory_summary",
    "daily factory summary": "generate_pdf_daily_factory_summary",
    "today's summary": "generate_pdf_daily_factory_summary",
    "owner review": "generate_pdf_owner_review",
    "urgent actions": "generate_pdf_urgent_actions",
    "running pos": "generate_pdf_running_pos",
    "active pos": "generate_pdf_active_pos",
    "delayed pos": "generate_pdf_delayed_pos",
    "fabric shortage": "generate_pdf_fabric_shortage",
    "fabric stock": "generate_pdf_fabric_stock",
    "mill orders": "generate_pdf_mill_orders",
    "late mill deliveries": "generate_pdf_late_mill_deliveries",
    "contractor delays": "generate_pdf_contractor_delay",
    "contractor performance": "generate_pdf_contractor_performance",
    "daily production": "generate_pdf_daily_production",
    "stage progress": "generate_pdf_stage_progress",
    "qc failures": "generate_pdf_qc_failures",
    "quality failures": "generate_pdf_qc_failures",
    "packing risk": "generate_pdf_packing_risk",
    "pending dispatch": "generate_pdf_pending_dispatch",
    "dispatch ready": "generate_pdf_dispatch_ready",
    "dispatch cost": "generate_pdf_dispatch_cost",
    "alerts": "generate_pdf_alerts",
    "reminders": "generate_pdf_reminders",
    "po status": "generate_pdf_po_status",
    "po stage progress": "generate_pdf_po_stage_progress",
}


def _resolve_report_type(raw: str) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if raw in REPORT_REGISTRY:
        return raw
    if key in REPORT_REGISTRY:
        return key
    return _NL_ALIASES.get(key)


@tool()
async def generate_pdf_report(report_type: str, filters_json: str = "") -> dict:
    """Generate a PDF report and return a download link.

    Use this when the owner asks to "prepare a PDF", "send me a report",
    "give me today's summary", "make a report of pending dispatch / fabric
    shortage / running POs / delayed POs / contractor delays / quality
    failures" etc. The tool runs synchronously; the returned ``download_url``
    is a button the UI will render directly under your reply.

    Common report types the owner may ask for:
    - "daily summary" / "daily factory summary" → today's full factory snapshot
    - "owner review" → executive summary across all stages
    - "urgent actions" → what needs the owner's attention right now
    - "running pos" / "active pos" → currently in-progress POs
    - "delayed pos" → POs missing their shipment date
    - "fabric shortage" → POs blocked by missing fabric
    - "fabric stock" → current inventory snapshot
    - "mill orders" → outstanding mill orders
    - "late mill deliveries" → overdue mill orders
    - "contractor delays" / "contractor performance"
    - "daily production" / "stage progress"
    - "qc failures" / "quality failures"
    - "pending dispatch" / "dispatch ready" / "dispatch cost"
    - "alerts" / "reminders"
    - "po status" (REQUIRES filters_json='{"po_number": "..."}')
    - "po stage progress" (REQUIRES filters_json='{"po_number": "..."}')

    Args:
        report_type: Either a registered report key
            (e.g. "generate_pdf_daily_factory_summary") or a natural-language
            name from the list above (e.g. "daily summary"). Case-insensitive.
        filters_json: Optional JSON string with filters. Most reports need no
            filters and accept "". PO-scoped reports need
            '{"po_number": "PO-2026-0042"}'.

    Returns:
        Dict with:
        - `status`: "completed" or "failed".
        - `report_type`: the resolved registry key.
        - `title`: human-readable report title.
        - `download_url`: relative URL to fetch the PDF (None on failure).
        - `report_id`: the report request UUID as a string.
        - `error`: error message on failure, else None.
        - `available_types`: list of supported names (only on validation error).
    """
    resolved = _resolve_report_type(report_type)
    if resolved is None:
        return {
            "status": "failed",
            "report_type": report_type,
            "title": None,
            "download_url": None,
            "report_id": None,
            "error": f"Unknown report type: {report_type!r}. Pick one of the supported names.",
            "available_types": sorted(_NL_ALIASES.keys()),
        }

    filters: dict = {}
    if filters_json.strip():
        try:
            parsed = json.loads(filters_json)
            if isinstance(parsed, dict):
                filters = parsed
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "report_type": resolved,
                "title": REPORT_REGISTRY[resolved].title,
                "download_url": None,
                "report_id": None,
                "error": "filters_json must be a valid JSON object string.",
            }

    session = current_session()
    service = ReportService(session)
    payload = ReportGenerateRequest(report_type=resolved, filters=filters)
    try:
        request = await service.create_request(payload, requested_by=None)
        generated = await service.generate_report(request.id)
    except ValueError as exc:
        return {
            "status": "failed",
            "report_type": resolved,
            "title": REPORT_REGISTRY[resolved].title,
            "download_url": None,
            "report_id": None,
            "error": str(exc),
        }

    success = generated.status.value == "completed"
    if success and generated.download_url:
        add_artifact(
            {
                "type": "pdf",
                "title": generated.title,
                "report_type": resolved,
                "report_id": str(generated.id),
                "download_url": generated.download_url,
            }
        )
    return {
        "status": generated.status.value,
        "report_type": resolved,
        "title": generated.title,
        "download_url": generated.download_url if success else None,
        "report_id": str(generated.id),
        "error": None if success else (generated.error_message or "report_generation_failed"),
    }
