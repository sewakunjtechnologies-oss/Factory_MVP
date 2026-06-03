from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.core.database import AsyncSessionLocal
from app.services.operational_backfill import ensure_all_operational_data, repair_future_actual_delivery_dates


async def main() -> None:
    async with AsyncSessionLocal() as db:
        repaired = await repair_future_actual_delivery_dates(db)
        await ensure_all_operational_data(db)
    print(f"Repaired future actual delivery dates: {repaired}")


if __name__ == "__main__":
    asyncio.run(main())
