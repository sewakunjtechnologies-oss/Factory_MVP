from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_audit_event(
    db: AsyncSession,
    *,
    action_type: str,
    entity_type: str,
    entity_id: str,
    purchase_order_id: UUID | None = None,
    performed_by: UUID | None = None,
    role: str | None = None,
    old_value_json: Optional[dict[str, Any]] = None,
    new_value_json: Optional[dict[str, Any]] = None,
    remarks: str | None = None,
) -> AuditLog:
    event = AuditLog(
        action_type=action_type,
        purchase_order_id=purchase_order_id,
        entity_type=entity_type,
        entity_id=entity_id,
        performed_by=performed_by,
        role=role,
        old_value_json=old_value_json,
        new_value_json=new_value_json,
        remarks=remarks,
    )
    db.add(event)
    await db.flush()
    return event

