from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


WriteIntent = Literal[
    "record_fabric_received",
    "record_partial_fabric_received",
    "verify_fabric",
    "record_fabric_ordered",
    "update_mill_delivery_date",
    "assign_fabric_to_cutting",
    "record_cutting_progress",
    "complete_cutting",
    "assign_to_stitching",
    "record_stitching_progress",
    "record_stitching_verification",
    "record_repair_quantity",
    "record_alteration_quantity",
    "record_rejected_quantity",
    "assign_to_packing",
    "record_packing_progress",
    "complete_packing",
    "record_dispatch",
    "record_partial_dispatch",
    "mark_po_completed",
    "update_po_status",
    "update_po_delivery_date",
    "update_po_priority",
    "add_po_remark",
    "generate_pdf_report",
    "bulk_data_update",
    "packing_material_update",
]

ReadIntent = Literal[
    "get_po_status",
    "get_fabric_shortage",
    "get_attention_today",
    "get_mill_orders",
    "get_late_mills",
    "get_dispatch_ready",
    "get_pending_dispatch",
    "get_contractor_delay",
    "get_packing_risk",
    "get_alerts",
    "get_reminders",
]


class OwnerAction(BaseModel):
    """Structured owner-command parse result.

    This is intentionally compact so deterministic parsing and Gemini fallback
    can share one safe shape. Route code only executes actions after this model
    validates and after the owner confirms the preview.
    """

    action_id: str = Field(default_factory=lambda: uuid4().hex)
    intent: WriteIntent | ReadIntent | Literal["ask_clarification", "unsupported"]
    confidence: float = Field(default=0.0, ge=0, le=1)
    po_number: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    confirmation_message: str | None = None


class PendingActionSnapshot(BaseModel):
    action_id: str
    intent: str
    po_number: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    confirmation_message: str | None = None


def today_iso() -> str:
    return date.today().isoformat()
