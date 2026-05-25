from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report_request import ReportRequest, ReportRequestStatus
from app.services.pdf_reports.data_access import FactoryAIDataAccess
from app.services.pdf_reports.report_registry import get_report_definition
from app.services.pdf_reports.report_renderer import render_report_pdf
from app.services.pdf_reports.report_schemas import ReportGenerateRequest, ReportPayload


class ReportService:
    def __init__(self, db: AsyncSession, reports_dir: Optional[Path] = None) -> None:
        self.db = db
        self.reports_dir = reports_dir or (Path(__file__).resolve().parents[3] / "generated_reports")

    async def create_request(self, payload: ReportGenerateRequest, requested_by: UUID | None) -> ReportRequest:
        definition = get_report_definition(payload.report_type)
        if definition is None:
            raise ValueError(f"Unsupported report type: {payload.report_type}")
        title = payload.title or definition.title
        record = ReportRequest(
            report_type=payload.report_type,
            requested_by=requested_by,
            filters_json=payload.filters or {},
            title=title,
            status=ReportRequestStatus.pending,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def list_requests(self, limit: int = 50) -> list[ReportRequest]:
        result = await self.db.execute(select(ReportRequest).order_by(ReportRequest.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def get_request(self, report_id: UUID) -> ReportRequest | None:
        result = await self.db.execute(select(ReportRequest).where(ReportRequest.id == report_id))
        return result.scalar_one_or_none()

    async def generate_report(self, report_id: UUID) -> ReportRequest:
        report = await self.get_request(report_id)
        if report is None:
            raise ValueError("Report request not found")

        report.status = ReportRequestStatus.generating
        report.error_message = None
        await self.db.commit()

        definition = get_report_definition(report.report_type)
        if definition is None:
            report.status = ReportRequestStatus.failed
            report.error_message = "Unsupported report type"
            await self.db.commit()
            return report

        missing = [key for key in definition.required_filters if not report.filters_json.get(key)]
        if missing:
            report.status = ReportRequestStatus.failed
            report.error_message = f"Missing required filters: {', '.join(missing)}"
            await self.db.commit()
            return report

        try:
            payload = await definition.generator(FactoryAIDataAccess(self.db), report.filters_json)
            if not isinstance(payload, ReportPayload):
                payload = ReportPayload.model_validate(payload)
            output_path = self._build_output_path(report.id, report.report_type)
            generated_by = str(report.requested_by) if report.requested_by else "owner"
            render_report_pdf(
                output_path,
                payload,
                report_type=report.report_type,
                generated_by=generated_by,
                filters=report.filters_json,
            )
            report.file_path = str(output_path)
            report.download_url = f"/api/v1/reports/pdf/{report.id}/download"
            report.status = ReportRequestStatus.completed
            report.completed_at = datetime.now(timezone.utc)
        except Exception as exc:  # pragma: no cover - safety branch
            report.status = ReportRequestStatus.failed
            report.error_message = str(exc)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    def _build_output_path(self, report_id: UUID, report_type: str) -> Path:
        safe_name = report_type.replace("/", "_").replace(" ", "_")
        filename = f"{safe_name}_{report_id}.pdf"
        return self.reports_dir / filename

