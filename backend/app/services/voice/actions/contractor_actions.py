"""Contractor lookup tool — Phase 2, real DB.

IMPORTANT: no `from __future__ import annotations` (breaks Gemini auto FC).
"""

from sqlalchemy import func, or_, select

from app.models.contractor import Contractor
from app.models.enums import ContractorType

from ..db_context import current_session
from ..tools import tool


_VALID_TYPES = {t.value for t in ContractorType}


@tool()
async def find_contractor(
    name: str = "",
    contractor_type: str = "",
    only_active: bool = True,
) -> dict:
    """Find contractors registered in the factory's system.

    Use this whenever the owner asks about a contractor by name, by what they
    do (cutting, stitching, packing, mill, transport, size inspection, quality
    check), or wants to see who's available for a given stage. Examples:
    "who are my stitching contractors?", "do we have a vendor called Sharma?",
    "show me active mill contractors".

    Args:
        name: Case-insensitive partial name match. Empty string means no name filter.
        contractor_type: One of "mill", "cutting", "stitching", "size_inspection",
            "quality_check", "packing", "transport". Empty string means no type filter.
        only_active: When True (default) only return contractors with is_active=True.

    Returns:
        A dict with:
        - `count`: number of contractors matched.
        - `contractors`: list of {id, name, contractor_type, phone, email, is_active}.
        - `filters_applied`: which filters were used.
        - `invalid_type`: present and True only when contractor_type was non-empty
          but not one of the valid values.
    """
    session = current_session()

    filters_applied: dict = {}
    invalid_type = False

    stmt = select(Contractor)
    if name.strip():
        pattern = f"%{name.strip().lower()}%"
        stmt = stmt.where(func.lower(Contractor.name).like(pattern))
        filters_applied["name"] = name.strip()
    if contractor_type.strip():
        normalized = contractor_type.strip().lower()
        if normalized not in _VALID_TYPES:
            invalid_type = True
        else:
            stmt = stmt.where(Contractor.contractor_type == ContractorType(normalized))
            filters_applied["contractor_type"] = normalized
    if only_active:
        stmt = stmt.where(Contractor.is_active.is_(True))
        filters_applied["only_active"] = True
    stmt = stmt.order_by(Contractor.contractor_type, Contractor.name).limit(50)

    if invalid_type:
        return {
            "count": 0,
            "contractors": [],
            "filters_applied": filters_applied,
            "invalid_type": True,
            "valid_types": sorted(_VALID_TYPES),
        }

    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return {
        "count": len(rows),
        "filters_applied": filters_applied,
        "contractors": [
            {
                "id": str(row.id),
                "name": row.name,
                "contractor_type": row.contractor_type.value
                if hasattr(row.contractor_type, "value")
                else str(row.contractor_type),
                "phone": row.phone,
                "email": row.email,
                "is_active": bool(row.is_active),
            }
            for row in rows
        ],
    }
