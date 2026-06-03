from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


SUPPORTED_REPORT_TYPES = {
    "generate_pdf_running_pos",
    "generate_pdf_active_pos",
    "generate_pdf_delayed_pos",
    "generate_pdf_po_status",
    "generate_pdf_po_stage_progress",
    "generate_pdf_fabric_shortage",
    "generate_pdf_fabric_stock",
    "generate_pdf_fabric_verification_pending",
    "generate_pdf_mill_orders",
    "generate_pdf_late_mill_deliveries",
    "generate_pdf_contractor_delay",
    "generate_pdf_contractor_performance",
    "generate_pdf_daily_production",
    "generate_pdf_stage_progress",
    "generate_pdf_qc_failures",
    "generate_pdf_packing_risk",
    "generate_pdf_pending_dispatch",
    "generate_pdf_june_dispatch",
    "generate_pdf_dispatch_ready",
    "generate_pdf_dispatch_cost",
    "generate_pdf_alerts",
    "generate_pdf_reminders",
    "generate_pdf_daily_factory_summary",
    "generate_pdf_urgent_actions",
    "generate_pdf_owner_review",
    "generate_pdf_mill_order_split",
    "generate_pdf_partial_mill_delivery",
    "generate_pdf_fabric_verification",
    "generate_pdf_fabric_mismatch_review",
    "generate_pdf_fabric_allocation_to_cutting",
    "generate_pdf_cutting_wastage",
    "generate_pdf_contractor_partial_return",
    "generate_pdf_stitching_verification",
    "generate_pdf_repair_rework",
    "generate_pdf_packing_capacity",
    "generate_pdf_dispatch_documentation",
    "generate_pdf_dispatch_exception",
    "generate_pdf_buyer_return",
    "generate_pdf_role_pending_tasks",
    "generate_pdf_escalated_reminders",
}

SUPPORTED_FORMAT_TYPES = {
    "summary",
    "detailed",
    "owner_review",
    "manager_review",
    "stage_wise",
    "contractor_wise",
    "po_wise",
    "date_wise",
}


class ReportGenerateRequest(BaseModel):
    report_type: str
    title: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)


class ReportRequestRead(BaseModel):
    id: UUID
    report_type: str
    title: str
    status: str
    filters_json: Dict[str, Any]
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ReportListRead(BaseModel):
    items: List[ReportRequestRead]


class ReportGenerateResponse(BaseModel):
    success: bool
    report_id: UUID
    report_type: str
    status: str
    message: str
    download_url: Optional[str] = None
    errors: List[str] = Field(default_factory=list)


class ReportPayload(BaseModel):
    title: str
    summary: Dict[str, Any] = Field(default_factory=dict)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
