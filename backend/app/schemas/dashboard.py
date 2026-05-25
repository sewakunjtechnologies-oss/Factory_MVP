from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import StageName
from app.schemas.reminder import ReminderRead
from app.schemas.alert import AlertRead


class PackingAnalysisRead(BaseModel):
    purchase_order_id: UUID
    remaining_qty: int
    days_left: int
    avg_per_packer: int
    actual_packers: int
    daily_target: float
    required_packers: float
    pieces_per_packer_per_day: float
    packing_risk: bool


class DashboardPORead(BaseModel):
    purchase_order_id: UUID
    po_number: str
    product: str
    status: str
    order_quantity_pcs: int
    completed_qty: int
    pending_qty: int
    bottleneck_stage: Optional[StageName]
    shipment_risk: bool
    next_urgent_action: str
    fabric_shortage_m: float


class BottleneckRead(BaseModel):
    stage: StageName
    pending_qty: int
    po_count: int


class OwnerDashboardRead(BaseModel):
    purchase_orders: List[DashboardPORead]
    alerts: List[AlertRead]
    reminders: List[ReminderRead]
    active_pos: int
    delayed_pos: int
    fabric_shortages: int
    shipment_risks: int
    pending_dispatch: int
    completed_today: int
    top_bottleneck_stages: List[BottleneckRead]
    action_cards: List[dict]
