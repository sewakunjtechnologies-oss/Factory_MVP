from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from app.core.database import get_db
from app.core.security import require_owner_or_manager
from app.models.user import User
from app.schemas.quotation import POQuotationRead
from app.services.quotation_service import build_po_quotation, generate_po_quotation_pdf

router = APIRouter()


@router.get("/{po_number}", response_model=POQuotationRead)
async def get_quotation(
    po_number: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> POQuotationRead:
    return await build_po_quotation(db, po_number)


@router.get("/{po_number}/pdf")
async def download_quotation_pdf(
    po_number: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner_or_manager)],
) -> FileResponse:
    quotation, path = await generate_po_quotation_pdf(db, po_number)
    filename = Path(path).name
    return FileResponse(path=str(path), media_type="application/pdf", filename=filename, headers={"X-PO-Number": quotation.po_number})
