from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import (
    require_cutting_verifier,
    require_fabric_allocator,
    require_fabric_verifier,
    require_manager,
    require_mill_followup_user,
    require_owner,
)
from app.models.user import User
from app.schemas.fabric import (
    FabricIssueToCuttingCreate,
    FabricIssueToCuttingRead,
    FabricMillOrderCreate,
    FabricMillOrderRead,
    MillDeliveryLotCreate,
    MillDeliveryLotRead,
    FabricReceiptRead,
    FabricVerificationUpdate,
    MillOrderShiftCreate,
    MillOrderSplitCreate,
    MillOrderSplitRead,
    MillFollowUpCreate,
    MillFollowUpRead,
)
from app.schemas.stage import (
    CuttingAnalysisCreate,
    CuttingAnalysisRead,
    MillWastageHistoryEntry,
    MillWastageRecordRead,
)
from app.services.fabric_operations import (
    create_fabric_mill_order,
    create_mill_order_split,
    create_mill_followup,
    cancel_mill_order,
    generate_fabric_followup_reminders,
    get_mill_wastage_history,
    issue_fabric_to_cutting,
    list_cutting_analysis,
    list_mill_delivery_lots,
    list_fabric_mill_orders,
    list_fabric_issues,
    list_mill_order_splits,
    list_late_mill_orders,
    list_mill_followups_due,
    list_mill_wastage_records,
    record_mill_delivery_lot,
    shift_mill_order_quantity,
    upsert_cutting_analysis,
    verify_fabric_receipt,
)

router = APIRouter()


@router.post("/mill-orders", response_model=FabricMillOrderRead, status_code=201)
async def create_mill_order(
    payload: FabricMillOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> FabricMillOrderRead:
    if payload.responsible_user_id is None:
        payload.responsible_user_id = user.id
    return await create_fabric_mill_order(db, payload)


@router.get("/mill-orders", response_model=List[FabricMillOrderRead])
async def list_mill_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
    purchase_order_id: Optional[UUID] = Query(default=None),
) -> List[FabricMillOrderRead]:
    return await list_fabric_mill_orders(db, purchase_order_id)


@router.get("/mill-orders/late", response_model=List[FabricMillOrderRead])
async def late_mill_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[FabricMillOrderRead]:
    return await list_late_mill_orders(db)


@router.post("/mill-followups", response_model=MillFollowUpRead, status_code=201)
async def create_followup(
    payload: MillFollowUpCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_mill_followup_user)],
) -> MillFollowUpRead:
    if payload.followup_by is None:
        payload.followup_by = user.id
    return await create_mill_followup(db, payload)


@router.get("/mill-followups/due", response_model=List[MillFollowUpRead])
async def due_followups(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[MillFollowUpRead]:
    return await list_mill_followups_due(db)


@router.post("/verify-receipt", response_model=FabricReceiptRead)
async def verify_receipt(
    payload: FabricVerificationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_fabric_verifier)],
) -> FabricReceiptRead:
    if payload.verified_by is None:
        payload.verified_by = user.id
    return await verify_fabric_receipt(db, payload)


@router.post("/issue-to-cutting", response_model=FabricIssueToCuttingRead, status_code=201)
async def create_fabric_issue(
    payload: FabricIssueToCuttingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_fabric_allocator)],
) -> FabricIssueToCuttingRead:
    if payload.issued_by is None:
        payload.issued_by = user.id
    return await issue_fabric_to_cutting(db, payload)


@router.get("/issue-to-cutting", response_model=List[FabricIssueToCuttingRead])
async def list_issues(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
    purchase_order_id: Optional[UUID] = Query(default=None),
) -> List[FabricIssueToCuttingRead]:
    return await list_fabric_issues(db, purchase_order_id)


@router.post("/cutting-analysis", response_model=CuttingAnalysisRead, status_code=201)
async def create_cutting_analysis(
    payload: CuttingAnalysisCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_cutting_verifier)],
) -> CuttingAnalysisRead:
    if payload.cutting_supervisor_id is None:
        payload.cutting_supervisor_id = user.id
    return await upsert_cutting_analysis(db, payload)


@router.get("/cutting-analysis", response_model=List[CuttingAnalysisRead])
async def list_cutting(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
    purchase_order_id: Optional[UUID] = Query(default=None),
) -> List[CuttingAnalysisRead]:
    return await list_cutting_analysis(db, purchase_order_id)


@router.get("/mill-wastage-history", response_model=List[MillWastageHistoryEntry])
async def mill_wastage_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[MillWastageHistoryEntry]:
    rows = await get_mill_wastage_history(db)
    return [MillWastageHistoryEntry(**row) for row in rows]


@router.get("/mill-wastage-records", response_model=List[MillWastageRecordRead])
async def mill_wastage_records(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
    mill_name: Optional[str] = Query(default=None),
    purchase_order_id: Optional[UUID] = Query(default=None),
) -> List[MillWastageRecordRead]:
    return await list_mill_wastage_records(db, mill_name=mill_name, purchase_order_id=purchase_order_id)


@router.post("/generate-reminders")
async def generate_reminders(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_manager)],
) -> Dict[str, str]:
    await generate_fabric_followup_reminders(db)
    return {"status": "ok"}


@router.post("/mill-orders/split", response_model=List[MillOrderSplitRead], status_code=201)
async def split_mill_order(
    payload: MillOrderSplitCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> List[MillOrderSplitRead]:
    return await create_mill_order_split(db, payload, actor_id=user.id)


@router.get("/mill-orders/split", response_model=List[MillOrderSplitRead])
async def list_splits(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_manager)],
    purchase_order_id: Optional[UUID] = Query(default=None),
) -> List[MillOrderSplitRead]:
    return await list_mill_order_splits(db, purchase_order_id)


@router.post("/mill-orders/{mill_order_id}/cancel", response_model=FabricMillOrderRead)
async def cancel_order(
    mill_order_id: UUID,
    reason: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> FabricMillOrderRead:
    return await cancel_mill_order(db, mill_order_id, reason=reason, actor_id=user.id)


@router.post("/mill-orders/shift", response_model=FabricMillOrderRead, status_code=201)
async def shift_order_qty(
    payload: MillOrderShiftCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> FabricMillOrderRead:
    return await shift_mill_order_quantity(db, payload, actor_id=user.id)


@router.post("/mill-delivery-lots", response_model=MillDeliveryLotRead, status_code=201)
async def create_delivery_lot(
    payload: MillDeliveryLotCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_mill_followup_user)],
) -> MillDeliveryLotRead:
    return await record_mill_delivery_lot(db, payload, actor_id=user.id)


@router.get("/mill-delivery-lots", response_model=List[MillDeliveryLotRead])
async def list_delivery_lots(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_mill_followup_user)],
    mill_order_id: Optional[UUID] = Query(default=None),
) -> List[MillDeliveryLotRead]:
    return await list_mill_delivery_lots(db, mill_order_id)
