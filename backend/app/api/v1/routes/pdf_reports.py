from __future__ import annotations

from pathlib import Path
from typing_extensions import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_owner
from app.models.user import User
from app.services.exceptions import DomainError
from app.services.pdf_reports.report_schemas import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportListRead,
    ReportRequestRead,
)
from app.services.pdf_reports.report_service import ReportService

router = APIRouter()


@router.post("/generate", response_model=ReportGenerateResponse)
async def generate_pdf_report(
    payload: ReportGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_owner)],
) -> ReportGenerateResponse:
    service = ReportService(db)
    try:
        request = await service.create_request(payload, current_user.id)
        generated = await service.generate_report(request.id)
    except ValueError as exc:
        raise DomainError(status_code=400, detail=str(exc)) from exc

    success = generated.status.value == "completed"
    return ReportGenerateResponse(
        success=success,
        report_id=generated.id,
        report_type=generated.report_type,
        status=generated.status.value,
        message=(
            "Report PDF generated successfully."
            if success
            else f"Report generation failed: {generated.error_message or 'unknown error'}"
        ),
        download_url=generated.download_url,
        errors=[] if success else [generated.error_message or "report_generation_failed"],
    )


@router.get("", response_model=ReportListRead)
async def list_pdf_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> ReportListRead:
    service = ReportService(db)
    rows = await service.list_requests()
    return ReportListRead(items=[ReportRequestRead.model_validate(row, from_attributes=True) for row in rows])


@router.get("/{report_id}", response_model=ReportRequestRead)
async def get_pdf_report(
    report_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> ReportRequestRead:
    service = ReportService(db)
    row = await service.get_request(report_id)
    if row is None:
        raise DomainError(status_code=404, detail="Report request not found")
    return ReportRequestRead.model_validate(row, from_attributes=True)


@router.get("/{report_id}/download")
async def download_pdf_report(
    report_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_owner)],
) -> FileResponse:
    service = ReportService(db)
    row = await service.get_request(report_id)
    if row is None:
        raise DomainError(status_code=404, detail="Report request not found")
    if row.status.value != "completed" or not row.file_path:
        raise DomainError(status_code=400, detail="Report is not ready for download")
    path = Path(row.file_path)
    if not path.exists():
        raise DomainError(status_code=404, detail="Report file not found on disk")
    return FileResponse(path=str(path), media_type="application/pdf", filename=path.name)

