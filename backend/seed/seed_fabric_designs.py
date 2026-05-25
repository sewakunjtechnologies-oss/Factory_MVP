"""Seed the fabric_designs table with 2 sample designs per category.

Generates simple PIL pattern images into ``backend/uploads/fabric_designs/``
and inserts matching ``FabricDesign`` rows. Idempotent: rows whose
``design_code`` already exists are skipped.

Run:
    cd backend
    python -m seed.seed_fabric_designs
"""
from __future__ import annotations

import asyncio
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.enums import FabricDesignCategory
from app.models.fabric_design import FabricDesign

UPLOAD_DIR = BACKEND_DIR / "uploads" / "fabric_designs"
IMAGE_URL_PREFIX = "/api/v1/fabric-designs/files"
IMAGE_SIZE = (600, 600)


@dataclass(frozen=True)
class SampleDesign:
    category: FabricDesignCategory
    design_code: str
    design_name: str
    pattern: str
    palette: tuple[str, ...]
    color_tags: list[str]
    description: str


SAMPLES: Sequence[SampleDesign] = (
    # Double bed sheet
    SampleDesign(
        FabricDesignCategory.double_bed_sheet,
        "DBL-STRIPE-001",
        "Classic Stripe Double Bed Sheet",
        pattern="stripe",
        palette=("#1f4e79", "#ffffff"),
        color_tags=["navy", "white"],
        description="Vertical navy and white stripes on premium cotton. Double bed size.",
    ),
    SampleDesign(
        FabricDesignCategory.double_bed_sheet,
        "DBL-FLORAL-002",
        "Garden Floral Double Bed Sheet",
        pattern="floral",
        palette=("#fde0e0", "#c0392b", "#27ae60"),
        color_tags=["pink", "red", "green"],
        description="Soft pink base with red blooms and green leaves. Double bed size.",
    ),
    # Single bed sheet
    SampleDesign(
        FabricDesignCategory.single_bed_sheet,
        "SGL-CHECK-001",
        "Cottage Check Single Bed Sheet",
        pattern="check",
        palette=("#ffffff", "#2980b9"),
        color_tags=["blue", "white"],
        description="Classic blue and white check, soft cotton, single bed size.",
    ),
    SampleDesign(
        FabricDesignCategory.single_bed_sheet,
        "SGL-DOT-002",
        "Polka Dot Single Bed Sheet",
        pattern="dot",
        palette=("#fff8e7", "#e67e22"),
        color_tags=["cream", "orange"],
        description="Warm cream base with orange polka dots. Single bed size.",
    ),
    # Fitted bed sheet
    SampleDesign(
        FabricDesignCategory.fitted_bed_sheet,
        "FIT-SOLID-001",
        "Solid Slate Fitted Bed Sheet",
        pattern="solid_texture",
        palette=("#34495e",),
        color_tags=["slate"],
        description="Solid slate fitted sheet with elastic edges. Subtle woven texture.",
    ),
    SampleDesign(
        FabricDesignCategory.fitted_bed_sheet,
        "FIT-STRIPE-002",
        "Thin Stripe Fitted Bed Sheet",
        pattern="stripe",
        palette=("#f5f5f5", "#16a085"),
        color_tags=["teal", "white"],
        description="Fine teal pinstripes on off-white. Fitted sheet, elastic corners.",
    ),
    # King bed sheet
    SampleDesign(
        FabricDesignCategory.king_bed_sheet,
        "KNG-PAISLEY-001",
        "Royal Paisley King Bed Sheet",
        pattern="paisley",
        palette=("#fcf3cf", "#8e44ad", "#d4ac0d"),
        color_tags=["cream", "purple", "gold"],
        description="Ornate paisley motifs on cream — king bed size, premium weave.",
    ),
    SampleDesign(
        FabricDesignCategory.king_bed_sheet,
        "KNG-DAMASK-002",
        "Damask King Bed Sheet",
        pattern="damask",
        palette=("#ffffff", "#7f8c8d"),
        color_tags=["white", "grey"],
        description="Subtle damask scrollwork on white. King bed size.",
    ),
    # Pillow
    SampleDesign(
        FabricDesignCategory.pillow,
        "PIL-FLORAL-001",
        "Spring Floral Pillow Cover",
        pattern="floral",
        palette=("#ffffff", "#e74c3c", "#27ae60"),
        color_tags=["white", "red", "green"],
        description="Bright spring florals on white — standard pillow cover.",
    ),
    SampleDesign(
        FabricDesignCategory.pillow,
        "PIL-DOT-002",
        "Mini Dot Pillow Cover",
        pattern="dot",
        palette=("#2c3e50", "#ecf0f1"),
        color_tags=["navy", "white"],
        description="Mini white dots on navy — standard pillow cover.",
    ),
)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _draw_stripe(img: Image.Image, palette: tuple[str, ...]) -> None:
    draw = ImageDraw.Draw(img)
    bg, fg = _hex_to_rgb(palette[0]), _hex_to_rgb(palette[1])
    img.paste(bg, (0, 0, *img.size))
    stripe_w = 28
    for x in range(0, img.size[0], stripe_w * 2):
        draw.rectangle((x, 0, x + stripe_w, img.size[1]), fill=fg)


def _draw_check(img: Image.Image, palette: tuple[str, ...]) -> None:
    draw = ImageDraw.Draw(img)
    bg, fg = _hex_to_rgb(palette[0]), _hex_to_rgb(palette[1])
    img.paste(bg, (0, 0, *img.size))
    cell = 40
    for y in range(0, img.size[1], cell):
        for x in range(0, img.size[0], cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle((x, y, x + cell, y + cell), fill=fg)


def _draw_dot(img: Image.Image, palette: tuple[str, ...]) -> None:
    draw = ImageDraw.Draw(img)
    bg, fg = _hex_to_rgb(palette[0]), _hex_to_rgb(palette[1])
    img.paste(bg, (0, 0, *img.size))
    step = 40
    radius = 8
    for y in range(step, img.size[1], step):
        for x in range(step, img.size[0], step):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fg)


def _draw_floral(img: Image.Image, palette: tuple[str, ...]) -> None:
    draw = ImageDraw.Draw(img)
    bg = _hex_to_rgb(palette[0])
    petal = _hex_to_rgb(palette[1])
    leaf = _hex_to_rgb(palette[2]) if len(palette) > 2 else petal
    img.paste(bg, (0, 0, *img.size))
    rng = random.Random(7)
    for _ in range(40):
        cx, cy = rng.randint(20, img.size[0] - 20), rng.randint(20, img.size[1] - 20)
        r = rng.randint(10, 22)
        for angle_offset in (-r, 0, r):
            draw.ellipse((cx - r + angle_offset, cy - r, cx + r + angle_offset, cy + r), fill=petal)
        draw.ellipse((cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2), fill=leaf)


def _draw_solid_texture(img: Image.Image, palette: tuple[str, ...]) -> None:
    base = _hex_to_rgb(palette[0])
    img.paste(base, (0, 0, *img.size))
    draw = ImageDraw.Draw(img)
    rng = random.Random(11)
    for _ in range(2500):
        x, y = rng.randint(0, img.size[0] - 1), rng.randint(0, img.size[1] - 1)
        shade = max(0, min(255, base[0] + rng.randint(-12, 12)))
        draw.point((x, y), fill=(shade, shade, shade))


def _draw_paisley(img: Image.Image, palette: tuple[str, ...]) -> None:
    draw = ImageDraw.Draw(img)
    bg = _hex_to_rgb(palette[0])
    a = _hex_to_rgb(palette[1])
    b = _hex_to_rgb(palette[2]) if len(palette) > 2 else a
    img.paste(bg, (0, 0, *img.size))
    rng = random.Random(13)
    for _ in range(18):
        cx, cy = rng.randint(50, img.size[0] - 50), rng.randint(50, img.size[1] - 50)
        for i in range(6):
            r = 38 - i * 5
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=a if i % 2 == 0 else b, width=2)


def _draw_damask(img: Image.Image, palette: tuple[str, ...]) -> None:
    draw = ImageDraw.Draw(img)
    bg = _hex_to_rgb(palette[0])
    fg = _hex_to_rgb(palette[1])
    img.paste(bg, (0, 0, *img.size))
    for y in range(40, img.size[1], 80):
        for x in range(40, img.size[0], 80):
            draw.ellipse((x - 24, y - 16, x + 24, y + 16), outline=fg, width=2)
            draw.ellipse((x - 16, y - 24, x + 16, y + 24), outline=fg, width=2)


_PATTERN_FNS = {
    "stripe": _draw_stripe,
    "check": _draw_check,
    "dot": _draw_dot,
    "floral": _draw_floral,
    "solid_texture": _draw_solid_texture,
    "paisley": _draw_paisley,
    "damask": _draw_damask,
}


def _generate_image(sample: SampleDesign, target: Path) -> None:
    img = Image.new("RGB", IMAGE_SIZE, "white")
    _PATTERN_FNS[sample.pattern](img, sample.palette)
    draw = ImageDraw.Draw(img)
    badge_h = 60
    draw.rectangle((0, IMAGE_SIZE[1] - badge_h, IMAGE_SIZE[0], IMAGE_SIZE[1]), fill=(0, 0, 0))
    draw.text((16, IMAGE_SIZE[1] - badge_h + 16), sample.design_code, fill=(255, 255, 255), font=_font(22))
    img.save(target, format="PNG", optimize=True)


async def _seed(session: AsyncSession) -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    existing = {
        code
        for code in (
            await session.execute(select(FabricDesign.design_code))
        ).scalars().all()
    }
    created = 0
    skipped = 0
    for sample in SAMPLES:
        if sample.design_code in existing:
            skipped += 1
            continue
        filename = f"seed_{sample.design_code.lower()}.png"
        target = UPLOAD_DIR / filename
        if not target.exists():
            _generate_image(sample, target)
        row = FabricDesign(
            category=sample.category,
            design_name=sample.design_name,
            design_code=sample.design_code,
            image_url=f"{IMAGE_URL_PREFIX}/{filename}",
            color_tags=sample.color_tags,
            description=sample.description,
            is_active=True,
        )
        session.add(row)
        created += 1
    await session.commit()
    print(f"Fabric design seed: created={created}, skipped_existing={skipped}")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await _seed(session)


if __name__ == "__main__":
    asyncio.run(main())
