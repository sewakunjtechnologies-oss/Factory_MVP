from __future__ import annotations

from typing import List

from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner, require_verifier
from app.models.user import User
from app.schemas.fabric import DebitNoteRead, FabricReceiptCreate, FabricReceiptRead, FabricReceiptResult, SupplierReturnRead
from app.services.fabric_planning import list_debit_notes, list_fabric_receipts, list_supplier_returns, receive_fabric

router = APIRouter()


@router.post("", response_model=FabricReceiptResult, status_code=201)
async def receive(
    payload: FabricReceiptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_verifier)],
) -> FabricReceiptResult:
    return await receive_fabric(db, payload)


@router.get("", response_model=List[FabricReceiptRead])
async def list_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_verifier)],
) -> List[FabricReceiptRead]:
    return await list_fabric_receipts(db)


@router.get("/supplier-returns", response_model=List[SupplierReturnRead])
async def returns(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[SupplierReturnRead]:
    return await list_supplier_returns(db)


@router.get("/debit-notes", response_model=List[DebitNoteRead])
async def debit_notes(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> List[DebitNoteRead]:
    return await list_debit_notes(db)
