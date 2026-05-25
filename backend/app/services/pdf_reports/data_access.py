from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.alert import Alert
from app.models.contractor import Contractor
from app.models.dispatch import DispatchLoad
from app.models.fabric_design import FabricDesign
from app.models.enums import FabricMillOrderStatus, StageName
from app.models.fabric import FabricIssueToCutting, FabricMillOrder, FabricPlan, FabricReceipt, MillDeliveryLot, MillFollowUp
from app.models.mill_requirement import MillOrderRequirement
from app.models.purchase_order import PurchaseOrder
from app.models.reminder import Reminder
from app.models.stage import ContractorAllocation, CuttingAnalysis, QualityFailure, StageProgressEntry, StageSummary


class FactoryAIDataAccess:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_po(self, po_reference: Optional[str]) -> Optional[PurchaseOrder]:
        if not po_reference:
            return None
        normalized = po_reference.strip().upper().replace(" ", "")
        clauses = [PurchaseOrder.po_number == normalized]
        if "#" in normalized:
            clauses.append(PurchaseOrder.po_number == normalized.replace("#", ""))
        if normalized.startswith("PO"):
            clauses.append(PurchaseOrder.po_number.ilike(f"%{normalized}%"))
        if "-" in normalized:
            clauses.append(PurchaseOrder.po_number.ilike(f"%{normalized.split('PO')[-1]}%"))

        result = await self.db.execute(
            select(PurchaseOrder)
            .where(or_(*clauses))
            .options(
                selectinload(PurchaseOrder.product),
                selectinload(PurchaseOrder.fabric_plan),
                selectinload(PurchaseOrder.stage_summaries),
                selectinload(PurchaseOrder.dispatch_loads),
            )
            .order_by(PurchaseOrder.created_at.desc())
        )
        return result.scalars().first()

    async def list_pos(self) -> list[PurchaseOrder]:
        result = await self.db.execute(
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.product),
                selectinload(PurchaseOrder.fabric_plan),
                selectinload(PurchaseOrder.stage_summaries),
                selectinload(PurchaseOrder.dispatch_loads),
            )
            .order_by(PurchaseOrder.promise_delivery_date.asc(), PurchaseOrder.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_stage_allocations(self, purchase_order_id: UUID) -> list[ContractorAllocation]:
        result = await self.db.execute(
            select(ContractorAllocation)
            .join(StageSummary, ContractorAllocation.stage_summary_id == StageSummary.id)
            .where(StageSummary.purchase_order_id == purchase_order_id)
            .options(selectinload(ContractorAllocation.contractor), selectinload(ContractorAllocation.stage_summary))
            .order_by(ContractorAllocation.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_stage_progress_entries(self, purchase_order_id: UUID) -> list[StageProgressEntry]:
        result = await self.db.execute(
            select(StageProgressEntry)
            .join(StageSummary, StageSummary.id == StageProgressEntry.stage_summary_id)
            .where(StageSummary.purchase_order_id == purchase_order_id)
            .order_by(StageProgressEntry.entry_date.desc(), StageProgressEntry.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_quality_failures(self, purchase_order_id: Optional[UUID] = None) -> list[QualityFailure]:
        statement = select(QualityFailure).join(StageSummary, StageSummary.id == QualityFailure.stage_summary_id)
        if purchase_order_id is not None:
            statement = statement.where(StageSummary.purchase_order_id == purchase_order_id)
        result = await self.db.execute(statement.order_by(QualityFailure.action_date.desc(), QualityFailure.created_at.desc()))
        return list(result.scalars().all())

    async def get_shortage_plans(self) -> list[tuple[PurchaseOrder, FabricPlan]]:
        result = await self.db.execute(
            select(PurchaseOrder, FabricPlan)
            .join(FabricPlan, FabricPlan.purchase_order_id == PurchaseOrder.id)
            .options(selectinload(PurchaseOrder.product))
            .where(FabricPlan.shortage_m > 0)
            .order_by(PurchaseOrder.promise_delivery_date.asc())
        )
        return list(result.all())

    async def get_mill_requirement(self, purchase_order_id: UUID) -> Optional[MillOrderRequirement]:
        result = await self.db.execute(
            select(MillOrderRequirement)
            .where(MillOrderRequirement.purchase_order_id == purchase_order_id)
            .order_by(MillOrderRequirement.created_at.desc())
        )
        return result.scalars().first()

    async def get_mill_orders(self, purchase_order_id: Optional[UUID] = None) -> list[FabricMillOrder]:
        statement = select(FabricMillOrder).order_by(FabricMillOrder.committed_delivery_date.asc(), FabricMillOrder.created_at.desc())
        if purchase_order_id is not None:
            statement = statement.where(FabricMillOrder.purchase_order_id == purchase_order_id)
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def get_partial_mill_deliveries(self) -> list[MillDeliveryLot]:
        result = await self.db.execute(
            select(MillDeliveryLot)
            .join(FabricMillOrder, FabricMillOrder.id == MillDeliveryLot.fabric_mill_order_id)
            .where(FabricMillOrder.status == FabricMillOrderStatus.partially_received)
            .order_by(MillDeliveryLot.received_date.desc(), MillDeliveryLot.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_late_mill_orders(self, on_date: Optional[date] = None) -> list[FabricMillOrder]:
        today = on_date or date.today()
        result = await self.db.execute(
            select(FabricMillOrder).where(
                FabricMillOrder.committed_delivery_date < today,
                FabricMillOrder.status.notin_([FabricMillOrderStatus.received, FabricMillOrderStatus.cancelled]),
            )
        )
        return list(result.scalars().all())

    async def get_mill_followups_due(self, on_date: Optional[date] = None) -> list[MillFollowUp]:
        today = on_date or date.today()
        result = await self.db.execute(
            select(MillFollowUp)
            .where(MillFollowUp.next_followup_date.is_not(None), MillFollowUp.next_followup_date <= today)
            .order_by(MillFollowUp.next_followup_date.asc(), MillFollowUp.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_fabric_verification_pending(self) -> list[FabricReceipt]:
        result = await self.db.execute(
            select(FabricReceipt)
            .where(FabricReceipt.verification_status == "pending")
            .order_by(FabricReceipt.received_at.desc(), FabricReceipt.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_fabric_mismatch_issues(self) -> list[FabricReceipt]:
        result = await self.db.execute(
            select(FabricReceipt)
            .where(FabricReceipt.verification_status.in_(["mismatch", "rejected", "returned"]))
            .order_by(FabricReceipt.received_at.desc(), FabricReceipt.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_verified_fabric_for_po(self, purchase_order_id: UUID) -> list[FabricReceipt]:
        result = await self.db.execute(
            select(FabricReceipt)
            .where(
                FabricReceipt.purchase_order_id == purchase_order_id,
                FabricReceipt.verification_status == "approved",
            )
            .order_by(FabricReceipt.received_at.desc())
        )
        return list(result.scalars().all())

    async def get_fabric_issues_to_cutting(self, purchase_order_id: UUID) -> list[FabricIssueToCutting]:
        result = await self.db.execute(
            select(FabricIssueToCutting)
            .where(FabricIssueToCutting.purchase_order_id == purchase_order_id)
            .order_by(FabricIssueToCutting.issue_date.desc(), FabricIssueToCutting.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_open_alerts(self) -> list[Alert]:
        result = await self.db.execute(select(Alert).where(Alert.is_resolved.is_(False)).order_by(Alert.created_at.desc()))
        return list(result.scalars().all())

    async def get_open_reminders(self) -> list[Reminder]:
        result = await self.db.execute(select(Reminder).where(Reminder.status == "open").order_by(Reminder.due_date.asc()))
        return list(result.scalars().all())

    async def get_dispatch_totals(self, purchase_order_id: UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(DispatchLoad.shipped_qty), 0)).where(DispatchLoad.purchase_order_id == purchase_order_id)
        )
        return int(result.scalar_one() or 0)

    async def get_dispatch_loads(self) -> list[DispatchLoad]:
        result = await self.db.execute(select(DispatchLoad).order_by(DispatchLoad.shipped_at.desc(), DispatchLoad.created_at.desc()))
        return list(result.scalars().all())

    async def get_dispatch_document_blocked_loads(self) -> list[DispatchLoad]:
        result = await self.db.execute(
            select(DispatchLoad)
            .where(DispatchLoad.document_status.in_(["blocked", "pending"]))
            .order_by(DispatchLoad.shipped_at.desc(), DispatchLoad.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_dispatch_ready_rows(self, today: Optional[date] = None) -> list[dict[str, Any]]:
        _ = today or date.today()
        pos = await self.list_pos()
        rows: list[dict[str, Any]] = []
        for po in pos:
            packing = next((stage for stage in po.stage_summaries if stage.stage == StageName.packing), None)
            if packing is None:
                continue
            shipped_qty = sum(load.shipped_qty for load in po.dispatch_loads)
            ready_qty = max(packing.approved_qty - shipped_qty, 0)
            if ready_qty <= 0:
                continue
            rows.append(
                {
                    "purchase_order_id": po.id,
                    "po_number": po.po_number,
                    "product": po.product.product_name if po.product else "Product",
                    "ready_qty": ready_qty,
                    "shipped_qty": shipped_qty,
                    "promise_delivery_date": po.promise_delivery_date,
                    "completion_date": _latest_dispatch_ready_date(po.stage_summaries),
                    "documentation_status": "Not tracked",
                }
            )
        return rows

    async def get_contractors(self) -> list[Contractor]:
        result = await self.db.execute(select(Contractor).where(Contractor.is_active.is_(True)).order_by(Contractor.name.asc()))
        return list(result.scalars().all())

    async def get_delayed_allocations(self, on_date: Optional[date] = None) -> list[ContractorAllocation]:
        today = on_date or date.today()
        result = await self.db.execute(
            select(ContractorAllocation)
            .where(
                ContractorAllocation.expected_completion_date.is_not(None),
                ContractorAllocation.expected_completion_date < today,
                ContractorAllocation.completed_qty < ContractorAllocation.issued_qty,
            )
            .options(selectinload(ContractorAllocation.contractor), selectinload(ContractorAllocation.stage_summary))
            .order_by(ContractorAllocation.expected_completion_date.asc())
        )
        return list(result.scalars().all())

    async def list_cutting_analysis(self) -> list[CuttingAnalysis]:
        result = await self.db.execute(select(CuttingAnalysis).order_by(CuttingAnalysis.updated_at.desc()))
        return list(result.scalars().all())

    async def get_pos_due_within(self, days: int) -> list[PurchaseOrder]:
        today = date.today()
        upper = today + timedelta(days=max(days, 0))
        result = await self.db.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.product), selectinload(PurchaseOrder.stage_summaries))
            .where(and_(PurchaseOrder.promise_delivery_date >= today, PurchaseOrder.promise_delivery_date <= upper))
            .order_by(PurchaseOrder.promise_delivery_date.asc())
        )
        return list(result.scalars().all())

    async def get_designs_by_category(self, category: str | None = None) -> list[FabricDesign]:
        statement = select(FabricDesign).where(FabricDesign.is_active.is_(True)).order_by(FabricDesign.design_code.asc())
        if category:
            statement = statement.where(FabricDesign.category == category)
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def search_designs(self, text: str, category: str | None = None) -> list[FabricDesign]:
        statement = select(FabricDesign).where(FabricDesign.is_active.is_(True))
        if category:
            statement = statement.where(FabricDesign.category == category)
        like = f"%{text.strip()}%"
        statement = statement.where(
            or_(
                FabricDesign.design_name.ilike(like),
                FabricDesign.design_code.ilike(like),
                FabricDesign.description.ilike(like),
            )
        ).order_by(FabricDesign.design_code.asc())
        result = await self.db.execute(statement)
        return list(result.scalars().all())

    async def get_unused_designs(self, category: str | None = None) -> list[FabricDesign]:
        used_subquery = select(PurchaseOrder.fabric_design_id).where(PurchaseOrder.fabric_design_id.is_not(None))
        statement = select(FabricDesign).where(
            FabricDesign.is_active.is_(True),
            FabricDesign.id.not_in(used_subquery),
        )
        if category:
            statement = statement.where(FabricDesign.category == category)
        statement = statement.order_by(FabricDesign.design_code.asc())
        result = await self.db.execute(statement)
        return list(result.scalars().all())


def _latest_dispatch_ready_date(stages: Iterable[StageSummary]) -> Optional[date]:
    packing = next((row for row in stages if row.stage == StageName.packing), None)
    if packing is None or packing.completed_qty <= 0:
        return None
    return date.today()


def decimal_to_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0
