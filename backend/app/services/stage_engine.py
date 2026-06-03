from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contractor import Contractor
from app.models.enums import POStatus, StageName, StageStatus, UserRole
from app.models.purchase_order import PurchaseOrder
from app.models.stage import (
    ContractorAllocation,
    PackingOutput,
    QualityFailure,
    StageCostEntry,
    StageProgressEntry,
    StageSummary,
)
from app.schemas.stage import (
    ContractorAllocationCreate,
    PackingOutputCreate,
    QualityFailureCreate,
    StageCostEntryCreate,
    StageProgressCreate,
)
from app.services.audit_service import log_audit_event
from app.services.exceptions import DomainError
from app.services.notification_service import create_notification
from app.services.purchase_order_service import STAGE_SEQUENCE
from app.services.reminder_service import upsert_reminder
from app.models.reminder import ReminderPriority, ReminderType
from app.services.user_service import get_or_create_owner


async def list_stage_summaries(db: AsyncSession, purchase_order_id: UUID) -> list[StageSummary]:
    result = await db.execute(
        select(StageSummary)
        .where(StageSummary.purchase_order_id == purchase_order_id)
        .order_by(StageSummary.sequence)
    )
    return list(result.scalars().all())


async def list_stage_progress_entries(db: AsyncSession, purchase_order_id: UUID) -> list[StageProgressEntry]:
    result = await db.execute(
        select(StageProgressEntry)
        .join(StageSummary)
        .where(StageSummary.purchase_order_id == purchase_order_id)
        .order_by(StageProgressEntry.entry_date.desc(), StageProgressEntry.created_at.desc())
    )
    return list(result.scalars().all())


async def list_quality_failures(db: AsyncSession, purchase_order_id: UUID) -> list[QualityFailure]:
    result = await db.execute(
        select(QualityFailure)
        .join(StageSummary)
        .where(StageSummary.purchase_order_id == purchase_order_id)
        .order_by(QualityFailure.action_date.desc(), QualityFailure.created_at.desc())
    )
    return list(result.scalars().all())


async def record_quality_failure(
    db: AsyncSession,
    payload: QualityFailureCreate,
    *,
    actor_id: UUID | None = None,
    actor_role: UserRole | None = None,
) -> QualityFailure:
    stage_summary = await _get_stage_summary_by_id(db, payload.stage_summary_id)
    _enforce_stage_verifier_role(stage_summary.stage, actor_role)

    allocation: ContractorAllocation | None = None
    if payload.allocation_id is not None:
        allocation = await db.get(ContractorAllocation, payload.allocation_id)
        if allocation is None or allocation.stage_summary_id != stage_summary.id:
            raise DomainError(status_code=400, detail="allocation does not belong to the selected PO stage")

    pending_resolution_qty = payload.failed_qty - payload.resolved_qty
    failure = QualityFailure(
        **payload.model_dump(),
        pending_resolution_qty=pending_resolution_qty,
    )
    db.add(failure)
    await db.flush()
    await log_audit_event(
        db,
        action_type="quality_failure_recorded",
        entity_type="quality_failure",
        entity_id=str(failure.id),
        purchase_order_id=stage_summary.purchase_order_id,
        performed_by=actor_id,
        role=actor_role.value if actor_role else None,
        new_value_json={
            "stage": stage_summary.stage.value,
            "failed_qty": payload.failed_qty,
            "resolved_qty": payload.resolved_qty,
            "action": payload.action.value,
        },
    )
    await db.commit()
    await db.refresh(failure)
    return failure


async def create_contractor(db: AsyncSession, payload: object) -> Contractor:
    contractor = Contractor(**payload.model_dump())
    db.add(contractor)
    await db.commit()
    await db.refresh(contractor)
    return contractor


async def list_contractors(db: AsyncSession) -> list[Contractor]:
    result = await db.execute(select(Contractor).order_by(Contractor.name))
    return list(result.scalars().all())


async def allocate_contractor(
    db: AsyncSession,
    payload: ContractorAllocationCreate,
    *,
    actor_id: UUID | None = None,
    actor_role: UserRole | None = None,
) -> ContractorAllocation:
    stage_summary = await _get_stage_summary_by_id(db, payload.stage_summary_id)
    _enforce_stage_allocator_role(stage_summary.stage, actor_role)
    contractor = await db.get(Contractor, payload.contractor_id)
    if contractor is None or not contractor.is_active:
        raise DomainError(status_code=404, detail="Active contractor not found")
    _ensure_positive(payload.issued_qty, "issued_qty")
    if payload.issued_qty > stage_summary.input_qty:
        raise DomainError(status_code=400, detail="issued_qty cannot exceed stage input quantity")

    issued_result = await db.execute(
        select(func.coalesce(func.sum(ContractorAllocation.issued_qty), 0)).where(
            ContractorAllocation.stage_summary_id == stage_summary.id
        )
    )
    already_issued = int(issued_result.scalar_one())
    if already_issued + payload.issued_qty > stage_summary.input_qty:
        raise DomainError(status_code=400, detail="total contractor issued quantity cannot exceed stage input quantity")

    allocation = ContractorAllocation(**payload.model_dump(), stage=stage_summary.stage)
    db.add(allocation)
    if payload.expected_completion_date is not None:
        reminder_type = ReminderType.cutting_due if stage_summary.stage == StageName.cutting else ReminderType.stitching_due if stage_summary.stage == StageName.stitching else ReminderType.packing_due
        await upsert_reminder(
            db,
            purchase_order_id=stage_summary.purchase_order_id,
            reminder_type=reminder_type,
            title=f"{stage_summary.stage.value.replace('_', ' ').title()} contractor due",
            message=f"{contractor.name} due on {payload.expected_completion_date.isoformat()}",
            due_date=payload.expected_completion_date,
            priority=ReminderPriority.medium,
            assigned_to=payload.contractor_id,
        )
    await db.flush()
    await log_audit_event(
        db,
        action_type=f"{stage_summary.stage.value}_allocated",
        entity_type="contractor_allocation",
        entity_id=str(allocation.id),
        purchase_order_id=stage_summary.purchase_order_id,
        performed_by=actor_id,
        role=actor_role.value if actor_role else None,
        new_value_json={"stage": stage_summary.stage.value, "issued_qty": allocation.issued_qty, "contractor_id": str(allocation.contractor_id)},
    )
    await db.commit()
    await db.refresh(allocation)
    return allocation


async def list_allocations(db: AsyncSession, purchase_order_id: UUID) -> list[ContractorAllocation]:
    result = await db.execute(
        select(ContractorAllocation)
        .join(StageSummary)
        .where(StageSummary.purchase_order_id == purchase_order_id)
        .options(selectinload(ContractorAllocation.contractor))
        .order_by(ContractorAllocation.created_at.desc())
    )
    return list(result.scalars().all())


async def record_stage_progress(
    db: AsyncSession,
    payload: StageProgressCreate,
    *,
    actor_id: UUID | None = None,
    actor_role: UserRole | None = None,
) -> StageProgressEntry:
    stage_summary = await _get_stage_summary(db, payload.purchase_order_id, payload.stage)
    _enforce_stage_verifier_role(stage_summary.stage, actor_role)
    allocation: ContractorAllocation | None = None
    _validate_progress_payload(payload)
    if payload.allocation_id is not None:
        allocation = await db.get(ContractorAllocation, payload.allocation_id)
        if allocation is None or allocation.stage_summary_id != stage_summary.id:
            raise DomainError(status_code=400, detail="allocation does not belong to the selected PO stage")

    if payload.completed_today > stage_summary.pending_qty:
        raise DomainError(status_code=400, detail="completed_today cannot exceed stage pending quantity")

    if allocation is not None and allocation.completed_qty + payload.completed_today > allocation.issued_qty:
        raise DomainError(status_code=400, detail="contractor completed quantity cannot exceed issued quantity")

    if payload.completed_today == 0 and payload.moved_to_next_stage_today == 0 and payload.delay_days == 0:
        raise DomainError(status_code=400, detail="progress entry must change production, movement, or delay")

    stage_summary.completed_qty += payload.completed_today
    stage_summary.approved_qty += payload.approved_today
    stage_summary.rejected_qty += payload.rejected_today
    stage_summary.repair_qty += payload.repair_today
    stage_summary.alter_qty += payload.alter_today
    stage_summary.pending_qty = stage_summary.input_qty - stage_summary.completed_qty
    _validate_stage_totals(stage_summary)
    _refresh_stage_status(stage_summary)

    if allocation is not None:
        allocation.completed_qty += payload.completed_today
        allocation.rejected_qty += payload.rejected_today
        allocation.repair_qty += payload.repair_today
        allocation.alter_qty += payload.alter_today
        allocation.delay_days = max(allocation.delay_days, payload.delay_days)
        _validate_allocation_totals(allocation)

    if payload.moved_to_next_stage_today > 0:
        await _move_to_next_stage(db, stage_summary, payload.moved_to_next_stage_today)

    if payload.delay_days > 0:
        stage_summary.status = StageStatus.delayed

    entry = StageProgressEntry(
        stage_summary_id=stage_summary.id,
        allocation_id=payload.allocation_id,
        entry_date=payload.entry_date,
        completed_today=payload.completed_today,
        approved_today=payload.approved_today,
        rejected_today=payload.rejected_today,
        repair_today=payload.repair_today,
        alter_today=payload.alter_today,
        moved_to_next_stage_today=payload.moved_to_next_stage_today,
        delay_days=payload.delay_days,
        remarks=payload.remarks,
    )
    db.add(entry)
    await db.flush()
    await log_audit_event(
        db,
        action_type=f"{stage_summary.stage.value}_progress_recorded",
        entity_type="stage_progress_entry",
        entity_id=str(entry.id),
        purchase_order_id=stage_summary.purchase_order_id,
        performed_by=actor_id,
        role=actor_role.value if actor_role else None,
        new_value_json={
            "completed_today": payload.completed_today,
            "approved_today": payload.approved_today,
            "rejected_today": payload.rejected_today,
            "repair_today": payload.repair_today,
            "alter_today": payload.alter_today,
            "moved_to_next_stage_today": payload.moved_to_next_stage_today,
        },
    )
    await _sync_po_status(db, stage_summary.purchase_order_id)
    await db.commit()
    await db.refresh(entry)
    return entry


async def update_packing_output(db: AsyncSession, payload: PackingOutputCreate) -> PackingOutput:
    stage_summary = await _get_stage_summary(db, payload.purchase_order_id, StageName.packing)
    if payload.packed_qty > stage_summary.approved_qty:
        raise DomainError(status_code=400, detail="packed_qty cannot exceed packing-ready quantity")
    result = await db.execute(
        select(PackingOutput).where(
            PackingOutput.purchase_order_id == payload.purchase_order_id,
            PackingOutput.output_date == payload.output_date,
        )
    )
    output = result.scalar_one_or_none()
    if output is None:
        output = PackingOutput(**payload.model_dump())
        db.add(output)
    else:
        for key, value in payload.model_dump().items():
            setattr(output, key, value)
    await db.flush()
    await log_audit_event(
        db,
        action_type="packing_output_entered",
        entity_type="packing_output",
        entity_id=str(output.id),
        purchase_order_id=payload.purchase_order_id,
        performed_by=payload.updated_by,
        role="packer_or_packing_allocator",
        new_value_json={"packed_qty": payload.packed_qty, "worker_count": payload.worker_count, "required_workers": str(payload.required_workers)},
    )
    await db.commit()
    await db.refresh(output)
    return output


async def list_packing_outputs(db: AsyncSession, purchase_order_id: UUID) -> list[PackingOutput]:
    result = await db.execute(
        select(PackingOutput)
        .where(PackingOutput.purchase_order_id == purchase_order_id)
        .order_by(PackingOutput.output_date.desc())
    )
    return list(result.scalars().all())


async def create_stage_cost_entry(db: AsyncSession, payload: StageCostEntryCreate) -> StageCostEntry:
    total_cost = payload.manual_cost or 0
    if payload.rate_per_piece is not None and payload.qty > 0:
        total_cost = payload.rate_per_piece * payload.qty
    cost_per_piece = 0 if payload.qty <= 0 else total_cost / payload.qty
    entry = StageCostEntry(
        **payload.model_dump(),
        total_stage_cost=total_cost,
        cost_per_piece=cost_per_piece,
    )
    db.add(entry)
    await db.flush()
    await log_audit_event(
        db,
        action_type="stage_cost_recorded",
        entity_type="stage_cost_entry",
        entity_id=str(entry.id),
        purchase_order_id=payload.purchase_order_id,
        new_value_json={"stage": payload.stage.value, "qty": payload.qty, "total_stage_cost": float(entry.total_stage_cost)},
    )
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_stage_cost_entries(db: AsyncSession, purchase_order_id: UUID) -> list[StageCostEntry]:
    result = await db.execute(
        select(StageCostEntry)
        .where(StageCostEntry.purchase_order_id == purchase_order_id)
        .order_by(StageCostEntry.created_at.desc())
    )
    return list(result.scalars().all())


async def get_stage_wise_cost_summary(db: AsyncSession, purchase_order_id: UUID) -> dict[str, object]:
    entries = await list_stage_cost_entries(db, purchase_order_id)
    stage_cost: dict[str, float] = {}
    total_cost = 0.0
    total_qty = 0
    for entry in entries:
        cost = float(entry.total_stage_cost)
        stage_cost[entry.stage.value] = stage_cost.get(entry.stage.value, 0.0) + cost
        total_cost += cost
        total_qty += max(entry.qty, 0)
    return {
        "purchase_order_id": str(purchase_order_id),
        "stage_costs": stage_cost,
        "total_stage_cost": round(total_cost, 2),
        "cost_per_piece": round(total_cost / total_qty, 4) if total_qty > 0 else 0,
    }


async def _move_to_next_stage(db: AsyncSession, stage_summary: StageSummary, quantity: int) -> None:
    _ensure_non_negative(quantity, "moved_to_next_stage_today")
    if stage_summary.stage == StageName.dispatch:
        raise DomainError(status_code=400, detail="dispatch is the final stage")

    available_to_move = stage_summary.approved_qty - stage_summary.moved_to_next_qty
    if quantity > available_to_move:
        raise DomainError(status_code=400, detail="next stage quantity cannot exceed approved quantity")

    next_stage = await _get_next_stage(db, stage_summary)
    if next_stage.input_qty + quantity > stage_summary.approved_qty:
        raise DomainError(status_code=400, detail="next stage input cannot exceed approved quantity from previous stage")
    next_stage.input_qty += quantity
    next_stage.pending_qty += quantity
    _validate_stage_totals(next_stage)
    if next_stage.status == StageStatus.not_started:
        next_stage.status = StageStatus.in_progress
    stage_summary.moved_to_next_qty += quantity


async def _get_stage_summary(db: AsyncSession, purchase_order_id: UUID, stage: StageName) -> StageSummary:
    result = await db.execute(
        select(StageSummary).where(
            StageSummary.purchase_order_id == purchase_order_id,
            StageSummary.stage == stage,
        )
    )
    stage_summary = result.scalar_one_or_none()
    if stage_summary is None:
        raise DomainError(status_code=404, detail="Stage summary not found")
    return stage_summary


async def _get_stage_summary_by_id(db: AsyncSession, stage_summary_id: UUID) -> StageSummary:
    stage_summary = await db.get(StageSummary, stage_summary_id)
    if stage_summary is None:
        raise DomainError(status_code=404, detail="Stage summary not found")
    return stage_summary


async def _get_next_stage(db: AsyncSession, stage_summary: StageSummary) -> StageSummary:
    index = STAGE_SEQUENCE.index(stage_summary.stage)
    next_stage_name = STAGE_SEQUENCE[index + 1]
    return await _get_stage_summary(db, stage_summary.purchase_order_id, next_stage_name)


def _refresh_stage_status(stage_summary: StageSummary) -> None:
    if stage_summary.input_qty == 0:
        stage_summary.status = StageStatus.not_started
    elif stage_summary.pending_qty == 0:
        stage_summary.status = StageStatus.completed
    else:
        stage_summary.status = StageStatus.in_progress


def _validate_progress_payload(payload: StageProgressCreate) -> None:
    for field_name in (
        "completed_today",
        "approved_today",
        "rejected_today",
        "repair_today",
        "alter_today",
        "moved_to_next_stage_today",
        "delay_days",
    ):
        _ensure_non_negative(getattr(payload, field_name), field_name)
    outcome_total = payload.approved_today + payload.rejected_today + payload.repair_today + payload.alter_today
    if payload.completed_today == 0 and outcome_total > 0:
        raise DomainError(status_code=400, detail="completed_today is required when outcome quantities are provided")
    if payload.completed_today > 0 and outcome_total != payload.completed_today:
        raise DomainError(status_code=400, detail="completed_today must equal approved + rejected + repair + alter")


def _validate_stage_totals(stage_summary: StageSummary) -> None:
    fields = (
        "input_qty",
        "completed_qty",
        "approved_qty",
        "rejected_qty",
        "repair_qty",
        "alter_qty",
        "moved_to_next_qty",
        "pending_qty",
    )
    for field_name in fields:
        _ensure_non_negative(getattr(stage_summary, field_name), field_name)
    if stage_summary.completed_qty > stage_summary.input_qty:
        raise DomainError(status_code=400, detail="stage completed quantity cannot exceed stage input quantity")
    outcome_total = stage_summary.approved_qty + stage_summary.rejected_qty + stage_summary.repair_qty + stage_summary.alter_qty
    if outcome_total > stage_summary.completed_qty:
        raise DomainError(status_code=400, detail="stage outcome quantities cannot exceed completed quantity")
    if stage_summary.moved_to_next_qty > stage_summary.approved_qty:
        raise DomainError(status_code=400, detail="moved quantity cannot exceed approved quantity")


def _validate_allocation_totals(allocation: ContractorAllocation) -> None:
    for field_name in ("issued_qty", "completed_qty", "rejected_qty", "repair_qty", "alter_qty", "delay_days"):
        _ensure_non_negative(getattr(allocation, field_name), field_name)
    if allocation.completed_qty > allocation.issued_qty:
        raise DomainError(status_code=400, detail="contractor completed quantity cannot exceed issued quantity")
    failed_total = allocation.rejected_qty + allocation.repair_qty + allocation.alter_qty
    if failed_total > allocation.completed_qty:
        raise DomainError(status_code=400, detail="contractor failure quantity cannot exceed completed quantity")


def _ensure_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise DomainError(status_code=400, detail=f"{field_name} must be greater than zero")


def _ensure_non_negative(value: int, field_name: str) -> None:
    if value < 0:
        raise DomainError(status_code=400, detail=f"{field_name} cannot be negative")


async def _sync_po_status(db: AsyncSession, purchase_order_id: UUID) -> None:
    po = await db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        return

    stages = await list_stage_summaries(db, purchase_order_id)
    dispatch_stage = next(stage for stage in stages if stage.stage == StageName.dispatch)
    if dispatch_stage.completed_qty >= po.order_quantity_pcs:
        po.status = POStatus.completed
        po.actual_delivery_date = date.today()
        return

    active = next((stage for stage in reversed(stages) if stage.input_qty > 0), None)
    if active is not None:
        stage_status_map = {
            StageName.fabric_ready: POStatus.fabric_ready,
            StageName.cutting: POStatus.cutting,
            StageName.stitching: POStatus.stitching,
            StageName.size_inspection: POStatus.size_inspection,
            StageName.quality_check: POStatus.quality_check,
            StageName.packing: POStatus.packing,
            StageName.dispatch: POStatus.dispatch,
        }
        po.status = stage_status_map[active.stage]


def _enforce_stage_allocator_role(_stage: StageName, role: UserRole | None) -> None:
    if role is None or role in {UserRole.owner, UserRole.manager}:
        return
    raise DomainError(status_code=403, detail=f"Role {role.value} cannot allocate work")


def _enforce_stage_verifier_role(_stage: StageName, role: UserRole | None) -> None:
    if role is None or role in {UserRole.owner, UserRole.manager}:
        return
    raise DomainError(status_code=403, detail=f"Role {role.value} cannot verify progress")
