from __future__ import annotations

from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.contractor import Contractor
from app.models.dispatch import DispatchLoad
from app.models.fabric_design import FabricDesign
from app.models.fabric import (
    DebitNote,
    FabricInventory,
    FabricIssueToCutting,
    FabricMillOrder,
    FabricPlan,
    FabricReceipt,
    MillDeliveryLot,
    MillFollowUp,
    MillOrderSplit,
    MillOrderStatusHistory,
    SupplierReturn,
)
from app.models.mill_requirement import MillOrderRequirement
from app.models.fabric_meter_receipt import FabricMeterReceipt
from app.models.notification import Notification
from app.models.packing_material import PackingMaterialInventory
from app.models.pieces_receipt import PiecesReceipt
from app.models.po_draft import PODraft
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.report_request import ReportRequest
from app.models.reminder import Reminder
from app.models.stage import (
    ContractorAllocation,
    CuttingAnalysis,
    PackingOutput,
    QualityFailure,
    StageCostEntry,
    StageProgressEntry,
    StageSummary,
)
from app.models.user import User
from app.models.vehicle import Vehicle

__all__ = [
    "Alert",
    "AuditLog",
    "Contractor",
    "ContractorAllocation",
    "CuttingAnalysis",
    "DispatchLoad",
    "FabricDesign",
    "DebitNote",
    "FabricInventory",
    "FabricIssueToCutting",
    "FabricMillOrder",
    "FabricPlan",
    "FabricReceipt",
    "MillDeliveryLot",
    "MillFollowUp",
    "MillOrderSplit",
    "MillOrderStatusHistory",
    "MillOrderRequirement",
    "FabricMeterReceipt",
    "Notification",
    "PackingMaterialInventory",
    "PackingOutput",
    "PiecesReceipt",
    "PODraft",
    "Product",
    "ProductFabricLine",
    "PurchaseOrder",
    "ReportRequest",
    "QualityFailure",
    "Reminder",
    "StageCostEntry",
    "StageProgressEntry",
    "StageSummary",
    "SupplierReturn",
    "User",
    "Vehicle",
]
