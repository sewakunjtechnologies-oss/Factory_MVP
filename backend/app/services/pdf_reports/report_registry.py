from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Tuple

from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.generators.alert_reports import generate_alerts_report, generate_reminders_report
from app.services.pdf_reports.generators.contractor_reports import (
    generate_contractor_delay_report,
    generate_contractor_performance_report,
)
from app.services.pdf_reports.generators.dispatch_reports import (
    generate_dispatch_cost_report,
    generate_dispatch_ready_report,
    generate_june_dispatch_report,
    generate_pending_dispatch_report,
)
from app.services.pdf_reports.generators.fabric_reports import (
    generate_fabric_shortage_report,
    generate_fabric_stock_report,
    generate_fabric_verification_pending_report,
)
from app.services.pdf_reports.generators.mill_reports import generate_late_mill_deliveries_report, generate_mill_orders_report
from app.services.pdf_reports.generators.owner_summary_reports import (
    generate_daily_factory_summary_report,
    generate_owner_review_report,
    generate_urgent_actions_report,
)
from app.services.pdf_reports.generators.po_reports import (
    generate_delayed_pos_report,
    generate_po_stage_progress_report,
    generate_po_status_report,
    generate_running_pos_report,
)
from app.services.pdf_reports.generators.production_reports import generate_daily_production_report, generate_stage_progress_report
from app.services.pdf_reports.generators.quality_reports import generate_qc_failures_report
from app.services.pdf_reports.generators.packing_reports import generate_packing_risk_report
from app.services.pdf_reports.generators.workflow_reports import (
    generate_buyer_return_report,
    generate_cutting_wastage_report,
    generate_dispatch_documentation_report,
    generate_dispatch_exception_report,
    generate_escalated_reminders_report,
    generate_fabric_allocation_to_cutting_report,
    generate_fabric_mismatch_review_report,
    generate_fabric_verification_report,
    generate_mill_order_split_report,
    generate_partial_mill_delivery_report,
    generate_repair_rework_report,
    generate_role_pending_tasks_report,
    generate_stitching_verification_report,
)
from app.services.pdf_reports.report_schemas import ReportPayload


GeneratorFunc = Callable[[FactoryAIDataAccess, Dict[str, Any]], Awaitable[ReportPayload]]


@dataclass(frozen=True)
class ReportDefinition:
    title: str
    generator: GeneratorFunc
    required_filters: Tuple[str, ...] = ()


REPORT_REGISTRY: Dict[str, ReportDefinition] = {
    "generate_pdf_running_pos": ReportDefinition("Running POs Report", generate_running_pos_report),
    "generate_pdf_active_pos": ReportDefinition("Active POs Report", generate_running_pos_report),
    "generate_pdf_delayed_pos": ReportDefinition("Delayed POs Report", generate_delayed_pos_report),
    "generate_pdf_po_status": ReportDefinition("PO Status Report", generate_po_status_report, ("po_number",)),
    "generate_pdf_po_stage_progress": ReportDefinition("PO Stage Progress Report", generate_po_stage_progress_report, ("po_number",)),
    "generate_pdf_fabric_shortage": ReportDefinition("Fabric Shortage Report", generate_fabric_shortage_report),
    "generate_pdf_fabric_stock": ReportDefinition("Fabric Stock Report", generate_fabric_stock_report),
    "generate_pdf_fabric_verification_pending": ReportDefinition(
        "Fabric Verification Pending Report",
        generate_fabric_verification_pending_report,
    ),
    "generate_pdf_mill_orders": ReportDefinition("Mill Orders Report", generate_mill_orders_report),
    "generate_pdf_late_mill_deliveries": ReportDefinition("Late Mill Deliveries Report", generate_late_mill_deliveries_report),
    "generate_pdf_contractor_delay": ReportDefinition("Contractor Delay Report", generate_contractor_delay_report),
    "generate_pdf_contractor_performance": ReportDefinition("Contractor Performance Report", generate_contractor_performance_report),
    "generate_pdf_daily_production": ReportDefinition("Daily Production Report", generate_daily_production_report),
    "generate_pdf_stage_progress": ReportDefinition("Stage Progress Report", generate_stage_progress_report),
    "generate_pdf_qc_failures": ReportDefinition("QC Failures Report", generate_qc_failures_report),
    "generate_pdf_packing_risk": ReportDefinition("Packing Risk Report", generate_packing_risk_report),
    "generate_pdf_pending_dispatch": ReportDefinition("Pending Dispatch Report", generate_pending_dispatch_report),
    "generate_pdf_june_dispatch": ReportDefinition("June Dispatch Report", generate_june_dispatch_report),
    "generate_pdf_dispatch_ready": ReportDefinition("Dispatch Ready Report", generate_dispatch_ready_report),
    "generate_pdf_dispatch_cost": ReportDefinition("Dispatch Cost Report", generate_dispatch_cost_report),
    "generate_pdf_alerts": ReportDefinition("Alerts Report", generate_alerts_report),
    "generate_pdf_reminders": ReportDefinition("Reminders Report", generate_reminders_report),
    "generate_pdf_daily_factory_summary": ReportDefinition("Daily Factory Summary Report", generate_daily_factory_summary_report),
    "generate_pdf_urgent_actions": ReportDefinition("Urgent Actions Report", generate_urgent_actions_report),
    "generate_pdf_owner_review": ReportDefinition("Owner Review Report", generate_owner_review_report),
    "generate_pdf_mill_order_split": ReportDefinition("Mill Order Split Report", generate_mill_order_split_report),
    "generate_pdf_partial_mill_delivery": ReportDefinition("Partial Mill Delivery Report", generate_partial_mill_delivery_report),
    "generate_pdf_fabric_verification": ReportDefinition("Fabric Verification Report", generate_fabric_verification_report),
    "generate_pdf_fabric_mismatch_review": ReportDefinition("Fabric Mismatch Review Report", generate_fabric_mismatch_review_report),
    "generate_pdf_fabric_allocation_to_cutting": ReportDefinition("Fabric Allocation To Cutting Report", generate_fabric_allocation_to_cutting_report),
    "generate_pdf_cutting_wastage": ReportDefinition("Cutting Wastage Report", generate_cutting_wastage_report),
    "generate_pdf_contractor_partial_return": ReportDefinition("Contractor Partial Return Report", generate_repair_rework_report),
    "generate_pdf_stitching_verification": ReportDefinition("Stitching Verification Report", generate_stitching_verification_report),
    "generate_pdf_repair_rework": ReportDefinition("Repair/Rework Report", generate_repair_rework_report),
    "generate_pdf_packing_capacity": ReportDefinition("Packing Capacity Report", generate_packing_risk_report),
    "generate_pdf_dispatch_documentation": ReportDefinition("Dispatch Documentation Report", generate_dispatch_documentation_report),
    "generate_pdf_dispatch_exception": ReportDefinition("Dispatch Exception Report", generate_dispatch_exception_report),
    "generate_pdf_buyer_return": ReportDefinition("Buyer Return Report", generate_buyer_return_report),
    "generate_pdf_role_pending_tasks": ReportDefinition("Role-wise Pending Task Report", generate_role_pending_tasks_report),
    "generate_pdf_escalated_reminders": ReportDefinition("Escalated Reminders Report", generate_escalated_reminders_report),
}


def get_report_definition(report_type: str) -> ReportDefinition | None:
    return REPORT_REGISTRY.get(report_type)
