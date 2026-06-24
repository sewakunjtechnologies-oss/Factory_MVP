from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alert import Alert
from app.models.contractor import Contractor
from app.models.enums import AlertPriority, AlertType, ContractorType, DispatchCostType, FabricMillOrderStatus, POStatus, StageName, StageStatus
from app.models.fabric import FabricMillOrder
from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import Reminder, ReminderPriority, ReminderStatus, ReminderType
from app.models.stage import StageSummary
from app.schemas.dispatch import DispatchLoadCreate
from app.schemas.mobile import MobileCategoryOption, MobileHomeSummary, MobilePOCard, MobilePOCreate, MobileTransitionPreview, MobileTransitionResult
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.stage import StageProgressCreate
from app.services.audit_service import log_audit_event
from app.services.dispatch_engine import create_dispatch_load, get_dispatch_summary
from app.services.exceptions import DomainError
from app.services.fabric_planning import build_or_refresh_fabric_plan
from app.services.operational_backfill import TERMINAL_PO_STATUSES, ensure_all_operational_data, ensure_po_operational_data
from app.services.purchase_order_service import create_purchase_order, get_purchase_order
from app.services.stage_engine import record_stage_progress


async def list_mobile_category_options(db: AsyncSession) -> list[MobileCategoryOption]:
    result = await db.execute(
        select(ProductFabricLine, Product)
        .join(Product, Product.id == ProductFabricLine.product_id)
        .order_by(Product.product_name.asc(), ProductFabricLine.fabric_code.asc())
    )
    options: list[MobileCategoryOption] = []
    for line, product in result.all():
        searchable = f"{product.product_name} {line.fabric_code} {product.size} {product.design} {product.color}"
        options.append(
            MobileCategoryOption(
                id=line.id,
                product_id=product.id,
                category_name=product.product_name,
                fabric_code=line.fabric_code,
                searchable_text=searchable,
                per_piece_meters=line.per_piece_meters,
                stock_meters=line.stock_meters,
                pieces_in_stock=line.pieces_in_stock,
            )
        )
    return options


async def create_mobile_po(db: AsyncSession, payload: MobilePOCreate, created_by: UUID | None) -> MobilePOCard:
    line = await db.get(ProductFabricLine, payload.category_option_id)
    if line is None:
        raise DomainError(status_code=404, detail="Product / fabric category not found")
    product = await db.get(Product, line.product_id)
    if product is None:
        raise DomainError(status_code=404, detail="Product not found")

    delivery_date, delivery_label, estimated = _resolve_delivery(payload)
    po_number = await _next_mobile_po_number(db, delivery_date)
    notes = "Created from mobile simplified flow."
    if estimated:
        notes += f" Delivery month selected as {payload.delivery_month}; planning date estimated as {delivery_date.isoformat()}."

    po = await create_purchase_order(
        db,
        PurchaseOrderCreate(
            po_number=po_number,
            product_id=product.id,
            order_quantity_pcs=payload.quantity,
            mrp=None,
            selling_price=None,
            order_date=date.today(),
            promise_delivery_date=delivery_date,
            notes=notes,
            custom_design_name=line.fabric_code,
            save_custom_design_to_library=False,
        ),
        created_by=created_by,
    )
    po.design_code_snapshot = line.fabric_code
    po.design_name_snapshot = line.fabric_code
    await build_or_refresh_fabric_plan(db, po)
    await log_audit_event(
        db,
        action_type="mobile_po_created",
        entity_type="purchase_order",
        entity_id=str(po.id),
        purchase_order_id=po.id,
        performed_by=created_by,
        role="owner_or_manager",
        new_value_json={"po_number": po.po_number, "fabric_code": line.fabric_code, "quantity": payload.quantity, "delivery_label": delivery_label},
    )
    await db.commit()
    fresh = await get_purchase_order(db, po.id)
    return await build_mobile_po_card(db, fresh)


async def list_mobile_pos(db: AsyncSession) -> list[MobilePOCard]:
    await ensure_all_operational_data(db)
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.product), selectinload(PurchaseOrder.fabric_plan), selectinload(PurchaseOrder.stage_summaries))
        .order_by(PurchaseOrder.promise_delivery_date.desc(), PurchaseOrder.po_number.asc())
    )
    return [await build_mobile_po_card(db, po) for po in result.scalars().all()]


async def get_mobile_home(db: AsyncSession) -> MobileHomeSummary:
    cards = await list_mobile_pos(db)
    active = [card for card in cards if card.status not in {"completed", "cancelled"} and not card.is_historical]
    urgent = [card for card in cards if card.warning]
    ready_dispatch = [card for card in cards if card.current_stage in {"READY_FOR_DISPATCH", "PACKING_COMPLETED"}]
    arrivals = await db.execute(
        select(func.count(FabricMillOrder.id)).where(
            FabricMillOrder.committed_delivery_date == date.today(),
            FabricMillOrder.status.notin_([FabricMillOrderStatus.received, FabricMillOrderStatus.cancelled]),
        )
    )
    return MobileHomeSummary(
        active_pos=len(active),
        urgent_attention_count=len(urgent),
        expected_arrivals_today=int(arrivals.scalar() or 0),
        ready_for_dispatch_count=len(ready_dispatch),
        cards=cards[:20],
    )


async def build_mobile_po_card(db: AsyncSession, po: PurchaseOrder) -> MobilePOCard:
    await ensure_po_operational_data(db, po, commit=False)
    product = po.product or (await db.get(Product, po.product_id) if po.product_id else None)
    plan = po.fabric_plan
    current_stage = _mobile_stage(po)
    warning = None
    if plan is not None and plan.shortage_m and plan.shortage_m > 0 and po.status not in TERMINAL_PO_STATUSES:
        warning = f"Fabric short by {plan.shortage_m} m"
    elif po.promise_delivery_date <= date.today() + timedelta(days=3) and po.status not in TERMINAL_PO_STATUSES:
        warning = "Delivery deadline approaching"
    return MobilePOCard(
        id=po.id,
        po_number=po.po_number,
        category_name=product.product_name if product else "Unknown",
        fabric_code=po.design_code_snapshot,
        quantity=po.order_quantity_pcs,
        delivery_date=po.promise_delivery_date,
        delivery_label=_delivery_label(po),
        current_stage=current_stage,
        status=po.status.value,
        warning=warning,
        is_historical=_is_historical(po),
        next_action_label=_next_action_label(current_stage),
        required_fabric_m=plan.total_required_m if plan else None,
        available_fabric_m=plan.available_m if plan else None,
        shortage_m=plan.shortage_m if plan else None,
    )


async def get_transition_preview(db: AsyncSession, po_id: UUID, action: str | None = None) -> MobileTransitionPreview:
    po = await get_purchase_order(db, po_id)
    current = _mobile_stage(po)
    next_stage, label, fields, can_execute, message = _transition_definition(current, action)
    return MobileTransitionPreview(
        po_id=po.id,
        po_number=po.po_number,
        current_stage=current,
        next_stage=next_stage,
        action_label=label,
        required_fields=fields,
        can_execute=can_execute,
        message=message,
    )


async def execute_transition(db: AsyncSession, po_id: UUID, *, action: str | None, values: dict, confirmed: bool, actor_id: UUID | None) -> MobileTransitionResult:
    preview = await get_transition_preview(db, po_id, action)
    if not confirmed:
        return MobileTransitionResult(success=False, message="Confirmation required.", preview=preview)
    po = await get_purchase_order(db, po_id)
    current = preview.current_stage
    if current == "FABRIC_SHORTAGE":
        await _prepare_mill_order(db, po, values, actor_id)
    elif current in {"FABRIC_READY", "FABRIC_VERIFIED"}:
        await _move_status(db, po, POStatus.cutting, actor_id, "mobile_move_to_cutting")
    elif current == "CUTTING":
        await _complete_stage(db, po, StageName.cutting, values, actor_id)
        po.status = POStatus.stitching
    elif current == "CUTTING_COMPLETED":
        await _move_status(db, po, POStatus.stitching, actor_id, "mobile_send_to_stitching")
    elif current == "STITCHING":
        await _complete_stage(db, po, StageName.stitching, values, actor_id, quality=True)
        po.status = POStatus.packing
    elif current == "STITCHING_COMPLETED":
        await _move_status(db, po, POStatus.packing, actor_id, "mobile_send_to_packing")
    elif current == "PACKING":
        await _complete_stage(db, po, StageName.packing, values, actor_id)
        po.status = POStatus.dispatch
    elif current in {"PACKING_COMPLETED", "READY_FOR_DISPATCH"}:
        await _dispatch(db, po, values)
    elif current in {"PARTIALLY_DISPATCHED", "DISPATCHED"}:
        await _complete_po(db, po, actor_id)
    else:
        raise DomainError(status_code=400, detail=f"No valid next action from {current}")
    await db.commit()
    fresh = await get_purchase_order(db, po.id)
    return MobileTransitionResult(success=True, message=f"Updated {fresh.po_number}. Stage is now {_mobile_stage(fresh).replace('_', ' ').title()}.", card=await build_mobile_po_card(db, fresh))


async def get_mobile_reminder_summary(db: AsyncSession) -> list[dict[str, str]]:
    await ensure_all_operational_data(db)
    result = await db.execute(
        select(Reminder)
        .where(Reminder.status == ReminderStatus.open, Reminder.due_date <= date.today())
        .order_by(Reminder.due_date.asc(), Reminder.created_at.asc())
        .limit(25)
    )
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "message": row.message,
            "due_date": row.due_date.isoformat(),
            "priority": row.priority.value,
            "purchase_order_id": str(row.purchase_order_id) if row.purchase_order_id else "",
        }
        for row in result.scalars().all()
    ]


async def snooze_mobile_reminder(db: AsyncSession, reminder_id: UUID, *, hours: int | None, until_date: date | None, actor_id: UUID | None) -> dict[str, str]:
    reminder = await db.get(Reminder, reminder_id)
    if reminder is None:
        raise DomainError(status_code=404, detail="Reminder not found")
    old_due = reminder.due_date
    if until_date is not None:
        reminder.due_date = until_date
    else:
        reminder.due_date = date.today() + timedelta(days=1)
    await log_audit_event(
        db,
        action_type="mobile_reminder_snoozed",
        entity_type="reminder",
        entity_id=str(reminder.id),
        purchase_order_id=reminder.purchase_order_id,
        performed_by=actor_id,
        role="owner_or_manager",
        old_value_json={"due_date": old_due.isoformat()},
        new_value_json={"due_date": reminder.due_date.isoformat()},
    )
    await db.commit()
    return {"message": f"Reminder snoozed to {reminder.due_date.isoformat()}."}


async def mark_mobile_reminder_handled(db: AsyncSession, reminder_id: UUID, actor_id: UUID | None) -> dict[str, str]:
    reminder = await db.get(Reminder, reminder_id)
    if reminder is None:
        raise DomainError(status_code=404, detail="Reminder not found")
    reminder.status = ReminderStatus.completed
    reminder.completed_at = datetime.utcnow()
    await log_audit_event(
        db,
        action_type="mobile_reminder_handled",
        entity_type="reminder",
        entity_id=str(reminder.id),
        purchase_order_id=reminder.purchase_order_id,
        performed_by=actor_id,
        role="owner_or_manager",
        new_value_json={"status": reminder.status.value},
    )
    await db.commit()
    return {"message": "Reminder marked handled."}


def _resolve_delivery(payload: MobilePOCreate) -> tuple[date, str, bool]:
    if payload.delivery_mode == "date" and payload.delivery_date is not None:
        return payload.delivery_date, payload.delivery_date.isoformat(), False
    year, month = [int(part) for part in str(payload.delivery_month).split("-")]
    last_day = calendar.monthrange(year, month)[1]
    estimated = date(year, month, last_day)
    return estimated, f"{calendar.month_name[month]} {year}", True


async def _next_mobile_po_number(db: AsyncSession, delivery_date: date) -> str:
    prefix = f"MOB-{delivery_date:%Y%m%d}"
    count = int((await db.execute(select(func.count(PurchaseOrder.id)).where(PurchaseOrder.po_number.like(f"{prefix}-%")))).scalar() or 0)
    return f"{prefix}-{count + 1:03d}"


def _is_historical(po: PurchaseOrder) -> bool:
    return "Historical Import" in (po.notes or "")


def _delivery_label(po: PurchaseOrder) -> str:
    if "Delivery month selected" in (po.notes or ""):
        return po.promise_delivery_date.strftime("%B %Y")
    return po.promise_delivery_date.isoformat()


def _mobile_stage(po: PurchaseOrder) -> str:
    if po.status == POStatus.shortage:
        return "FABRIC_SHORTAGE"
    if po.status == POStatus.fabric_ready:
        return "FABRIC_READY"
    if po.status == POStatus.cutting:
        return "CUTTING"
    if po.status == POStatus.stitching:
        return "STITCHING"
    if po.status in {POStatus.size_inspection, POStatus.quality_check}:
        return "STITCHING_COMPLETED"
    if po.status == POStatus.packing:
        return "PACKING"
    if po.status == POStatus.dispatch:
        return "READY_FOR_DISPATCH"
    if po.status == POStatus.partially_dispatched:
        return "PARTIALLY_DISPATCHED"
    if po.status == POStatus.dispatched_with_exception:
        return "DISPATCHED"
    if po.status == POStatus.completed and _is_historical(po):
        return "DISPATCHED"
    if po.status == POStatus.completed:
        return "COMPLETED"
    if po.status == POStatus.cancelled:
        return "CANCELLED"
    return "PO_CREATED"


def _next_action_label(stage: str) -> str:
    return {
        "PO_CREATED": "Check Fabric",
        "FABRIC_SHORTAGE": "Prepare Mill Order",
        "FABRIC_READY": "Move to Cutting",
        "FABRIC_ORDERED": "Mark Fabric Received",
        "FABRIC_RECEIVED": "Verify Fabric",
        "FABRIC_VERIFIED": "Send to Cutting",
        "CUTTING": "Complete Cutting",
        "CUTTING_COMPLETED": "Send to Stitching",
        "STITCHING": "Complete Stitching",
        "STITCHING_COMPLETED": "Send to Packing",
        "PACKING": "Complete Packing",
        "PACKING_COMPLETED": "Dispatch PO",
        "READY_FOR_DISPATCH": "Dispatch PO",
        "PARTIALLY_DISPATCHED": "Dispatch Remaining",
        "DISPATCHED": "Complete PO",
    }.get(stage, "View PO")


def _transition_definition(stage: str, action: str | None) -> tuple[str, str, list[dict], bool, str]:
    fields_by_stage = {
        "FABRIC_SHORTAGE": ("FABRIC_ORDERED", "Prepare Mill Order", [
            {"name": "mill_name", "label": "Which mill?", "type": "text", "required": True},
            {"name": "meters", "label": "How many meters?", "type": "number", "required": True},
            {"name": "expected_delivery_date", "label": "Expected delivery date", "type": "date", "required": True},
            {"name": "rate_per_meter", "label": "Rate per meter", "type": "number", "required": False},
        ]),
        "FABRIC_READY": ("CUTTING", "Move to Cutting", []),
        "FABRIC_VERIFIED": ("CUTTING", "Send to Cutting", []),
        "CUTTING": ("CUTTING_COMPLETED", "Complete Cutting", [
            {"name": "completed_pieces", "label": "How many pieces completed?", "type": "number", "required": True},
            {"name": "rejected_pieces", "label": "Rejected quantity", "type": "number", "required": False, "default": 0},
            {"name": "repair_pieces", "label": "Repair quantity", "type": "number", "required": False, "default": 0},
        ]),
        "CUTTING_COMPLETED": ("STITCHING", "Send to Stitching", [
            {"name": "contractor", "label": "To whom was it sent?", "type": "text", "required": True},
            {"name": "pieces", "label": "How many pieces?", "type": "number", "required": True},
            {"name": "expected_date", "label": "Expected back date", "type": "date", "required": True},
        ]),
        "STITCHING": ("STITCHING_COMPLETED", "Complete Stitching", [
            {"name": "returned_pieces", "label": "Returned pieces", "type": "number", "required": True},
            {"name": "approved_pieces", "label": "Approved pieces", "type": "number", "required": True},
            {"name": "repair_pieces", "label": "Repair pieces", "type": "number", "required": False, "default": 0},
            {"name": "alteration_pieces", "label": "Alteration pieces", "type": "number", "required": False, "default": 0},
            {"name": "rejected_pieces", "label": "Rejected pieces", "type": "number", "required": False, "default": 0},
        ]),
        "STITCHING_COMPLETED": ("PACKING", "Send to Packing", [{"name": "pieces", "label": "Approved pieces", "type": "number", "required": True}]),
        "PACKING": ("PACKING_COMPLETED", "Complete Packing", [
            {"name": "packed_pieces", "label": "How many pieces packed?", "type": "number", "required": True},
            {"name": "damaged_pieces", "label": "Damaged/pending pieces", "type": "number", "required": False, "default": 0},
        ]),
        "READY_FOR_DISPATCH": ("PARTIALLY_DISPATCHED", "Dispatch PO", [{"name": "dispatch_pieces", "label": "Pieces being dispatched", "type": "number", "required": True}]),
        "PACKING_COMPLETED": ("PARTIALLY_DISPATCHED", "Dispatch PO", [{"name": "dispatch_pieces", "label": "Pieces being dispatched", "type": "number", "required": True}]),
        "PARTIALLY_DISPATCHED": ("DISPATCHED", "Dispatch Remaining", [{"name": "dispatch_pieces", "label": "Pieces being dispatched", "type": "number", "required": True}]),
        "DISPATCHED": ("COMPLETED", "Complete PO", []),
    }
    if stage not in fields_by_stage:
        return stage, "No next action", [], False, f"No valid next action from {stage}."
    next_stage, label, fields = fields_by_stage[stage]
    return next_stage, label, fields, True, f"{label} is available."


async def _prepare_mill_order(db: AsyncSession, po: PurchaseOrder, values: dict, actor_id: UUID | None) -> None:
    for field in ("mill_name", "meters", "expected_delivery_date"):
        if not values.get(field):
            raise DomainError(status_code=400, detail=f"{field} is required")
    meters = Decimal(str(values["meters"]))
    if meters <= 0:
        raise DomainError(status_code=400, detail="meters must be greater than zero")
    order = FabricMillOrder(
        purchase_order_id=po.id,
        mill_name=str(values["mill_name"]),
        ordered_meters=meters,
        ordered_rate_per_meter=Decimal(str(values["rate_per_meter"])) if values.get("rate_per_meter") else None,
        committed_delivery_date=date.fromisoformat(str(values["expected_delivery_date"])),
        status=FabricMillOrderStatus.ordered,
        remarks="Created from mobile workflow.",
    )
    db.add(order)
    await db.flush()
    db.add(Alert(purchase_order_id=po.id, alert_type=AlertType.stock_shortage, priority=AlertPriority.high, title="Fabric shortage actioned", message=f"Mill order prepared for {po.po_number}."))
    await log_audit_event(db, action_type="mobile_mill_order_prepared", entity_type="fabric_mill_order", entity_id=str(order.id), purchase_order_id=po.id, performed_by=actor_id, role="owner_or_manager", new_value_json={"mill_name": order.mill_name, "ordered_meters": str(meters)})


async def _move_status(db: AsyncSession, po: PurchaseOrder, status: POStatus, actor_id: UUID | None, action_type: str) -> None:
    old_status = po.status.value
    po.status = status
    await log_audit_event(db, action_type=action_type, entity_type="purchase_order", entity_id=str(po.id), purchase_order_id=po.id, performed_by=actor_id, role="owner_or_manager", old_value_json={"status": old_status}, new_value_json={"status": po.status.value})


async def _complete_stage(db: AsyncSession, po: PurchaseOrder, stage: StageName, values: dict, actor_id: UUID | None, quality: bool = False) -> None:
    completed = int(values.get("returned_pieces") or values.get("completed_pieces") or values.get("packed_pieces") or values.get("pieces") or 0)
    if completed <= 0:
        raise DomainError(status_code=400, detail="completed quantity is required")
    approved = int(values.get("approved_pieces") or max(0, completed - int(values.get("repair_pieces") or 0) - int(values.get("alteration_pieces") or 0) - int(values.get("rejected_pieces") or 0)))
    rejected = int(values.get("rejected_pieces") or 0)
    repair = int(values.get("repair_pieces") or 0)
    alter = int(values.get("alteration_pieces") or 0)
    if approved + rejected + repair + alter != completed:
        raise DomainError(status_code=400, detail="completed must equal approved + rejected + repair + alteration")
    summary = next((row for row in po.stage_summaries if row.stage == stage), None)
    if summary and summary.input_qty <= 0:
        summary.input_qty = po.order_quantity_pcs
        summary.pending_qty = po.order_quantity_pcs
        summary.status = StageStatus.in_progress
        await db.flush()
    await record_stage_progress(
        db,
        StageProgressCreate(
            purchase_order_id=po.id,
            stage=stage,
            entry_date=date.today(),
            completed_today=completed,
            approved_today=approved,
            rejected_today=rejected,
            repair_today=repair,
            alter_today=alter,
            moved_to_next_stage_today=approved,
            remarks="Created from mobile workflow.",
        ),
        actor_id=actor_id,
        actor_role=None,
    )


async def _dispatch(db: AsyncSession, po: PurchaseOrder, values: dict) -> None:
    qty = int(values.get("dispatch_pieces") or 0)
    if qty <= 0:
        raise DomainError(status_code=400, detail="dispatch_pieces is required")
    await create_dispatch_load(
        db,
        DispatchLoadCreate(
            purchase_order_id=po.id,
            load_number=f"MOBILE-{po.po_number}-{date.today().isoformat()}",
            shipped_qty=qty,
            cost_type=DispatchCostType.manual,
            manual_cost=Decimal("0"),
            shipped_at=date.fromisoformat(str(values.get("dispatch_date") or date.today().isoformat())),
            transporter_name=values.get("transporter") or None,
            document_status="complete",
            remarks=values.get("remarks") or "Created from mobile workflow.",
        ),
    )


async def _complete_po(db: AsyncSession, po: PurchaseOrder, actor_id: UUID | None) -> None:
    summary = await get_dispatch_summary(db, po.id)
    if summary.pending_dispatch > 0:
        raise DomainError(status_code=400, detail=f"Cannot complete. {summary.pending_dispatch} pieces are still pending.")
    await _move_status(db, po, POStatus.completed, actor_id, "mobile_po_completed")
