"""Dispatch load planner — CBM + weight bin-packing.

The owner picks a vehicle (a known CBM + weight capacity) and tells us which
categories to prioritize. For each fabric line, the system already knows:
  - pieces_in_stock           (how many finished pieces are ready to ship)
  - pieces_per_bale           (how many pieces are bundled into one bale)
  - bale_size_cbm             (volume of one bale)
  - bale_weight_kg            (weight of one bale)

The planner walks the categories in the user-specified order. For each
category, it walks the eligible fabric lines (sorted by largest stock first
so we ship the most urgent things first). For each line it figures out the
*maximum* number of bales that fits in the remaining CBM AND remaining weight,
capped by the bales that actually exist in stock. Whatever's left over (truck
capacity OR pieces) carries forward to the next category — exactly matching
the owner's spec:

    "if there is space after completing category A pieces, then it should
     calculate how many pieces of category B can be go in that container."
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_fabric_line import ProductFabricLine
from app.models.vehicle import Vehicle
from app.services.exceptions import DomainError


@dataclass(slots=True)
class PlanItem:
    product_fabric_line_id: UUID
    category: str
    fabric_code: str
    bales: int
    pieces: int
    cbm: Decimal
    weight_kg: Decimal


@dataclass(slots=True)
class PlanResult:
    vehicle_id: UUID
    vehicle_name: str
    cbm_capacity: Decimal
    max_weight_kg: Decimal
    used_cbm: Decimal
    used_weight_kg: Decimal
    fill_pct_cbm: float
    fill_pct_weight: float
    total_bales: int
    total_pieces: int
    items: list[PlanItem]
    leftover: list[dict]  # categories / lines we couldn't fit


async def plan_dispatch(
    db: AsyncSession,
    *,
    vehicle_id: UUID,
    category_priority: Sequence[str],
) -> PlanResult:
    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None or not vehicle.is_active:
        raise DomainError(status_code=404, detail="Vehicle not found or inactive")

    cbm_cap = Decimal(vehicle.cbm_capacity)
    weight_cap = Decimal(vehicle.max_weight_kg)

    if not category_priority:
        raise DomainError(status_code=400, detail="Provide at least one category in priority order.")

    # Pull every fabric line whose category appears in the priority list, plus
    # its category name. We filter to lines that actually have stock + bale info.
    stmt = (
        select(ProductFabricLine, Product)
        .join(Product, Product.id == ProductFabricLine.product_id)
        .where(Product.product_name.in_(list(category_priority)))
    )
    rows = (await db.execute(stmt)).all()
    lines_by_category: dict[str, list[tuple[ProductFabricLine, Product]]] = {}
    for line, product in rows:
        lines_by_category.setdefault(product.product_name, []).append((line, product))

    remaining_cbm = cbm_cap
    remaining_weight = weight_cap
    items: list[PlanItem] = []
    leftover: list[dict] = []

    for category in category_priority:
        cat_lines = lines_by_category.get(category, [])
        # Within a category, ship the lines with the most stock first — it's
        # usually the safest default. (The owner can override by re-ordering
        # categories, or we can add a per-line priority knob later.)
        cat_lines.sort(key=lambda lp: lp[0].pieces_in_stock, reverse=True)

        for line, _product in cat_lines:
            stock = int(line.pieces_in_stock or 0)
            pp_bale = int(line.pieces_per_bale or 0)
            bale_cbm = Decimal(line.bale_size_cbm or 0)
            bale_kg = Decimal(line.bale_weight_kg or 0)

            if stock <= 0 or pp_bale <= 0 or bale_cbm <= 0 or bale_kg <= 0:
                if stock > 0:
                    leftover.append({
                        "category": category,
                        "fabric_code": line.fabric_code,
                        "reason": "missing bale spec (pieces_per_bale / bale_size_cbm / bale_weight_kg = 0)",
                        "available_pieces": stock,
                    })
                continue

            available_bales = stock // pp_bale
            if available_bales == 0:
                continue

            # How many bales fit, capped by CBM, by weight, and by stock.
            cbm_fits = int(remaining_cbm // bale_cbm) if bale_cbm > 0 else 0
            weight_fits = int(remaining_weight // bale_kg) if bale_kg > 0 else 0
            bales_to_load = min(available_bales, cbm_fits, weight_fits)

            if bales_to_load <= 0:
                # Truck is full enough that even one bale of this fabric doesn't fit.
                leftover.append({
                    "category": category,
                    "fabric_code": line.fabric_code,
                    "reason": f"no room — needs {float(bale_cbm):.4f} m³ + {float(bale_kg):.2f} kg per bale",
                    "available_pieces": stock,
                })
                continue

            cbm_used = bale_cbm * bales_to_load
            weight_used = bale_kg * bales_to_load
            pieces_loaded = pp_bale * bales_to_load

            items.append(
                PlanItem(
                    product_fabric_line_id=line.id,
                    category=category,
                    fabric_code=line.fabric_code,
                    bales=bales_to_load,
                    pieces=pieces_loaded,
                    cbm=cbm_used,
                    weight_kg=weight_used,
                )
            )

            remaining_cbm -= cbm_used
            remaining_weight -= weight_used

            # Anything left over in stock that didn't fit (because cap was hit) is
            # reported so the owner knows what's bumped to the next truck.
            unloaded_pieces = stock - pieces_loaded
            if unloaded_pieces > 0 and bales_to_load < available_bales:
                leftover.append({
                    "category": category,
                    "fabric_code": line.fabric_code,
                    "reason": "truck full",
                    "available_pieces": unloaded_pieces,
                })

    used_cbm = cbm_cap - remaining_cbm
    used_weight = weight_cap - remaining_weight

    return PlanResult(
        vehicle_id=vehicle.id,
        vehicle_name=vehicle.name,
        cbm_capacity=cbm_cap,
        max_weight_kg=weight_cap,
        used_cbm=used_cbm,
        used_weight_kg=used_weight,
        fill_pct_cbm=_pct(used_cbm, cbm_cap),
        fill_pct_weight=_pct(used_weight, weight_cap),
        total_bales=sum(i.bales for i in items),
        total_pieces=sum(i.pieces for i in items),
        items=items,
        leftover=leftover,
    )


def _pct(used: Decimal, cap: Decimal) -> float:
    if cap <= 0:
        return 0.0
    return float((used / cap) * 100).__round__(1)


# Small helper used by tests and the API for ceiling division — keeping it
# explicit so the rounding behaviour is obvious to readers.
def ceil_div(a: int, b: int) -> int:
    return math.ceil(a / b) if b else 0
