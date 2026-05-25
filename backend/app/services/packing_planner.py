"""Packing planner — pure math, no DB access.

Two modes:

  Forward:  total_pieces, packers, target_days  → pieces per packer per day (ceil)
  Reverse:  total_pieces, packers, per_packer_per_day → days needed (ceil)

Both round up: if you can pack 234.6 pcs/day per packer you must plan for 235.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator


PlanMode = Literal["forward", "reverse"]


class PackingPlanRequest(BaseModel):
    mode: PlanMode
    total_pieces: int = Field(gt=0, description="Total pieces that need to be packed in this run")
    packers: int = Field(gt=0, description="Number of in-house packers available")
    target_days: int | None = Field(default=None, ge=1, description="Forward mode: target days to finish")
    per_packer_per_day: int | None = Field(default=None, ge=1, description="Reverse mode: each packer's daily output")

    @model_validator(mode="after")
    def _validate_mode_inputs(self) -> "PackingPlanRequest":
        if self.mode == "forward" and self.target_days is None:
            raise ValueError("forward mode requires target_days")
        if self.mode == "reverse" and self.per_packer_per_day is None:
            raise ValueError("reverse mode requires per_packer_per_day")
        return self


class PackingPlanResponse(BaseModel):
    mode: PlanMode
    total_pieces: int
    packers: int
    target_days: int | None
    per_packer_per_day: int
    days_required: int
    pieces_per_day_total: int
    explanation: str


def plan(req: PackingPlanRequest) -> PackingPlanResponse:
    if req.mode == "forward":
        # Floor of total_pieces / target_days / packers — but we always round UP per packer/day
        # so that the plan over-delivers rather than under-delivers.
        assert req.target_days is not None  # validator guarantees this
        per_packer = math.ceil(req.total_pieces / (req.packers * req.target_days))
        pieces_per_day_total = per_packer * req.packers
        days_required = math.ceil(req.total_pieces / pieces_per_day_total)
        return PackingPlanResponse(
            mode="forward",
            total_pieces=req.total_pieces,
            packers=req.packers,
            target_days=req.target_days,
            per_packer_per_day=per_packer,
            days_required=days_required,
            pieces_per_day_total=pieces_per_day_total,
            explanation=(
                f"To pack {req.total_pieces} pcs in {req.target_days} day(s) with {req.packers} packer(s), "
                f"each packer needs to do at least {per_packer} pcs/day. "
                f"That's {pieces_per_day_total} pcs/day from the whole team."
            ),
        )

    # reverse mode
    assert req.per_packer_per_day is not None
    pieces_per_day_total = req.per_packer_per_day * req.packers
    days_required = math.ceil(req.total_pieces / pieces_per_day_total)
    return PackingPlanResponse(
        mode="reverse",
        total_pieces=req.total_pieces,
        packers=req.packers,
        target_days=None,
        per_packer_per_day=req.per_packer_per_day,
        days_required=days_required,
        pieces_per_day_total=pieces_per_day_total,
        explanation=(
            f"With {req.packers} packer(s) each doing {req.per_packer_per_day} pcs/day, "
            f"the team packs {pieces_per_day_total} pcs/day. "
            f"Packing {req.total_pieces} pcs will take {days_required} day(s)."
        ),
    )
