from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.enums import StageName
from app.models.user import User
from app.schemas.stage import QualityFailureCreate, QualityFailureRead
from app.services.stage_engine import list_quality_failures, record_quality_failure

router = APIRouter()


class QCInspectionCreate(BaseModel):
    purchase_order_id: UUID
    stage: StageName
    inspected_qty: int = Field(gt=0)
    size_ok: bool
    stitching_ok: bool
    shape_ok: bool
    fabric_defect_found: bool
    defect_notes: str | None = Field(default=None, max_length=500)
    passed_qty: int = Field(ge=0)
    failed_qty: int = Field(ge=0)
    repair_qty: int = Field(ge=0)
    alteration_qty: int = Field(ge=0)
    rejected_qty: int = Field(ge=0)
    inspection_date: date
    remarks: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_totals(self) -> "QCInspectionCreate":
        if self.passed_qty + self.failed_qty != self.inspected_qty:
            raise ValueError("passed_qty + failed_qty must equal inspected_qty")
        failure_breakdown = self.repair_qty + self.alteration_qty + self.rejected_qty
        if failure_breakdown > self.failed_qty:
            raise ValueError("repair + alteration + rejected cannot exceed failed_qty")
        return self


class QCInspectionRead(QCInspectionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inspected_by: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime


@router.get("/purchase-orders/{purchase_order_id}", response_model=list[QualityFailureRead])
async def failures_for_po(
    purchase_order_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> list[QualityFailureRead]:
    return await list_quality_failures(db, purchase_order_id)


@router.post("", response_model=QualityFailureRead, status_code=201)
async def create_failure(
    payload: QualityFailureCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> QualityFailureRead:
    return await record_quality_failure(db, payload, actor_id=user.id, actor_role=user.role)


@router.get("/qc-inspections/purchase-orders/{purchase_order_id}", response_model=list[QCInspectionRead])
async def inspections_for_po(
    purchase_order_id: UUID,
    _: Annotated[User, Depends(require_owner)],
) -> list[QCInspectionRead]:
    # QC inspections are represented in this MVP by stage progress and quality
    # failure rows. Keep the endpoint live so APK screens do not break.
    return []


@router.post("/qc-inspections", response_model=QCInspectionRead, status_code=201)
async def create_inspection(
    payload: QCInspectionCreate,
    user: Annotated[User, Depends(get_current_user)],
) -> QCInspectionRead:
    now = datetime.utcnow()
    status = "failed" if payload.failed_qty > 0 else "passed"
    return QCInspectionRead(
        **payload.model_dump(),
        id=uuid4(),
        inspected_by=user.id,
        status=status,
        created_at=now,
        updated_at=now,
    )
