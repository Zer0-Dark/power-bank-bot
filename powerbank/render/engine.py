"""Pillow helpers for drawing onto template images.

**Arabic shaping.** Arabic letters change form by position and must be reordered
into visual order. There are two ways to get that:

- *Legacy*: `arabic-reshaper` + `python-bidi` map text to Unicode Presentation
  Forms (U+FE70-FEFF). This only works with fonts that still carry those
  codepoints. Most modern fonts -- Readex Pro included -- carry none of them, so
  this path renders nothing but tofu boxes.
- *Correct*: HarfBuzz shaping via Raqm, which drives the font's OpenType GSUB
  tables. This is what Pillow's RAQM layout engine does, and it handles the
  bidi algorithm for mixed Arabic/Latin values too.

We use Raqm and pass raw logical text. Raqm ships inside Pillow's binary wheels,
so it is present in the Docker image as well as locally, but `require_shaping()`
checks explicitly rather than silently producing broken cards.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features


class ShapingUnavailable(RuntimeError):
    """Pillow was built without Raqm, so Arabic cannot be shaped."""


def require_shaping() -> None:
    """Fail loudly at startup rather than rendering tofu at request time."""
    if not features.check("raqm"):
        raise ShapingUnavailable(
            "Pillow lacks Raqm support, so Arabic text cannot be shaped. "
            "Install a Pillow binary wheel (pip install --force-reinstall Pillow) "
            "or the system libraqm package."
        )


@lru_cache(maxsize=64)
def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


@dataclass(frozen=True, slots=True)
class Field:
    """Where one value goes, in original-template pixel coordinates."""

    x: int
    y: int
    max_width: int
    font_size: int

    @classmethod
    def from_dict(cls, raw: dict) -> Field:
        return cls(
            x=raw["center"][0],
            y=raw["center"][1],
            max_width=raw["max_width"],
            font_size=raw["font_size"],
        )


@dataclass(frozen=True, slots=True)
class Layout:
    """A template plus the boxes its values are drawn into.

    Coordinates live in JSON beside the artwork, not in code -- these get nudged
    many times and nobody should need to edit Python to move a label.
    """

    template: Path
    font: Path
    color: tuple[int, int, int]
    fields: dict[str, Field]
    min_font_size: int
    output_width: int | None

    @classmethod
    def load(cls, path: Path, assets_dir: Path) -> Layout:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            template=assets_dir / "templates" / raw["template"],
            font=assets_dir / "fonts" / raw["font"],
            color=tuple(raw["color"]),
            min_font_size=raw.get("min_font_size", 24),
            output_width=raw.get("output_width"),
            fields={name: Field.from_dict(f) for name, f in raw["fields"].items()},
        )


ELLIPSIS = "…"


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    field: Field,
    min_size: int,
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Return the largest font, and the text, that fit the field's width.

    Shrinking beats overflowing: a long name spilling past the bar looks broken,
    a slightly smaller one does not. If even `min_size` will not fit, the text
    is truncated -- the renderer must never draw outside its box, whatever it
    is handed.
    """
    size = field.font_size
    while size > min_size:
        font = load_font(font_path, size)
        if draw.textlength(text, font=font) <= field.max_width:
            return font, text
        size -= 2

    font = load_font(font_path, min_size)
    if draw.textlength(text, font=font) <= field.max_width:
        return font, text

    clipped = text
    while clipped and draw.textlength(clipped + ELLIPSIS, font=font) > field.max_width:
        clipped = clipped[:-1]
    return font, clipped + ELLIPSIS


def render(layout: Layout, values: dict[str, str]) -> BytesIO:
    """Draw `values` onto the template and return a PNG buffer.

    CPU-bound: async callers must wrap this in `asyncio.to_thread`.
    """
    image = Image.open(layout.template).convert("RGBA")
    draw = ImageDraw.Draw(image)
    font_path = str(layout.font)

    for name, field in layout.fields.items():
        raw = values.get(name)
        if raw in (None, ""):
            continue
        font, text = fit_text(draw, str(raw), font_path, field, layout.min_font_size)
        # "mm" anchors on the middle of the glyph box in both axes, so a value
        # stays centred in its bar regardless of ascenders or descenders.
        draw.text((field.x, field.y), text, font=font, fill=layout.color, anchor="mm")

    # Text is drawn at full template resolution and downscaled afterwards, so
    # glyph edges stay smooth. Telegram re-compresses photos anyway, so sending
    # the full 3080px original just costs upload time.
    if layout.output_width and layout.output_width < image.width:
        ratio = layout.output_width / image.width
        image = image.resize(
            (layout.output_width, round(image.height * ratio)), Image.LANCZOS
        )

    buffer = BytesIO()
    # optimize=True costs seconds of CPU to save ~1% here -- a bad trade for a
    # per-request render.
    image.convert("RGB").save(buffer, format="PNG", compress_level=6)
    buffer.seek(0)
    return buffer
