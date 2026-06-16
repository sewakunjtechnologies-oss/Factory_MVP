from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.core.database import AsyncSessionLocal, create_all_tables
from app.services.packing_material_service import backfill_june_packing_materials


async def main() -> None:
    await create_all_tables()
    async with AsyncSessionLocal() as db:
        summary = await backfill_june_packing_materials(db)
        print("Packing material backfill completed.")
        print(f"June POs scanned: {summary.purchase_orders_scanned}")
        print(f"Rows created: {summary.rows_created}")
        print(f"Rows updated: {summary.rows_updated}")


if __name__ == "__main__":
    asyncio.run(main())
