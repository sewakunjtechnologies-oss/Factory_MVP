from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    owner = "owner"
    manager = "manager"


class POStatus(str, Enum):
    draft = "draft"
    fabric_check_pending = "fabric_check_pending"
    fabric_ready = "fabric_ready"
    shortage = "shortage"
    cutting = "cutting"
    stitching = "stitching"
    size_inspection = "size_inspection"
    quality_check = "quality_check"
    packing = "packing"
    dispatch = "dispatch"
    partially_dispatched = "partially_dispatched"
    dispatched_with_exception = "dispatched_with_exception"
    completed = "completed"
    delayed = "delayed"
    cancelled = "cancelled"


class ContractorType(str, Enum):
    mill = "mill"
    cutting = "cutting"
    stitching = "stitching"
    size_inspection = "size_inspection"
    quality_check = "quality_check"
    packing = "packing"
    transport = "transport"


class StageName(str, Enum):
    fabric_ready = "fabric_ready"
    cutting = "cutting"
    stitching = "stitching"
    size_inspection = "size_inspection"
    quality_check = "quality_check"
    packing = "packing"
    dispatch = "dispatch"


class StageStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    delayed = "delayed"
    blocked = "blocked"


class ReceiptStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    failed = "failed"
    returned = "returned"


class ShortageStatus(str, Enum):
    open = "open"
    action_taken = "action_taken"
    closed = "closed"


class FabricPlanStatus(str, Enum):
    fabric_ready = "fabric_ready"
    shortage = "shortage"


class DispatchCostType(str, Enum):
    invoice_percent = "invoice_percent"
    cbm = "cbm"
    manual = "manual"
    vehicle_capacity = "vehicle_capacity"


class AlertType(str, Enum):
    stock_shortage = "stock_shortage"
    stage_delay = "stage_delay"
    contractor_delay = "contractor_delay"
    shipment_risk = "shipment_risk"
    packing_risk = "packing_risk"
    high_rejection = "high_rejection"
    high_cutting_wastage = "high_cutting_wastage"
    capacity_risk = "capacity_risk"
    cutting_underutilization = "cutting_underutilization"
    stitching_underutilization = "stitching_underutilization"
    packing_underutilization = "packing_underutilization"


class AlertPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class QualityAction(str, Enum):
    repair_in_factory = "repair_in_factory"
    return_to_contractor = "return_to_contractor"
    reject = "reject"


class FabricMillOrderStatus(str, Enum):
    not_ordered = "not_ordered"
    ordered = "ordered"
    in_followup = "in_followup"
    partially_received = "partially_received"
    received = "received"
    delayed = "delayed"
    cancelled = "cancelled"


class FabricVerificationStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    mismatch = "mismatch"
    rejected = "rejected"
    returned = "returned"


class FabricVerificationAction(str, Enum):
    accept = "accept"
    return_to_supplier = "return_to_supplier"
    reopen_shortage = "reopen_shortage"
    adjust_consumption = "adjust_consumption"
    hold = "hold"


class CapacityStage(str, Enum):
    cutting = "cutting"
    stitching = "stitching"
    packing = "packing"


class ProductType(str, Enum):
    single_bedsheet = "single_bedsheet"
    double_bedsheet = "double_bedsheet"
    king_bedsheet = "king_bedsheet"
    pillow = "pillow"
    fitted_sheet = "fitted_sheet"
    other = "other"


class FabricDesignCategory(str, Enum):
    double_bed_sheet = "double_bed_sheet"
    single_bed_sheet = "single_bed_sheet"
    fitted_bed_sheet = "fitted_bed_sheet"
    king_bed_sheet = "king_bed_sheet"
    pillow = "pillow"
    other = "other"


class PODesignStatus(str, Enum):
    selected_from_library = "selected_from_library"
    custom_design = "custom_design"
    not_provided = "not_provided"
