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
    """Where one value goes, in original-template pixel coordinates.

    `font` overrides the layout's default face for this field only -- the card
    mixes an Arabic display face for the names, a Latin one for the username and
    a numeric one for the account number, so no single file covers every box.

    `anchor` is a Pillow text anchor for the point: the default ``"mm"`` centres
    the value in its bar, while ``"lm"`` pins its left edge -- for a value that
    must start right after a label baked into the art, whatever its length.
    """

    x: int
    y: int
    max_width: int
    font_size: int
    font: str | None = None
    anchor: str = "mm"

    @classmethod
    def from_dict(cls, raw: dict) -> Field:
        return cls(
            x=raw["center"][0],
            y=raw["center"][1],
            max_width=raw["max_width"],
            font_size=raw["font_size"],
            font=raw.get("font"),
            anchor=raw.get("anchor", "mm"),
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
    fonts: dict[str, Path]
    min_font_size: int
    output_width: int | None
    stroke_width: int
    stroke_color: tuple[int, int, int]
    gradient: tuple[tuple[int, int, int], tuple[int, int, int]] | None

    @classmethod
    def load(cls, path: Path, assets_dir: Path) -> Layout:
        raw = json.loads(path.read_text(encoding="utf-8"))
        fonts_dir = assets_dir / "fonts"
        default_font = raw["font"]
        fields = {name: Field.from_dict(f) for name, f in raw["fields"].items()}
        gradient = raw.get("gradient")
        return cls(
            template=assets_dir / "templates" / raw["template"],
            font=fonts_dir / default_font,
            color=tuple(raw["color"]),
            fields=fields,
            fonts={
                name: fonts_dir / (field.font or default_font) for name, field in fields.items()
            },
            min_font_size=raw.get("min_font_size", 24),
            output_width=raw.get("output_width"),
            stroke_width=raw.get("stroke_width", 0),
            stroke_color=tuple(raw.get("stroke_color", (255, 255, 255))),
            gradient=((tuple(gradient[0]), tuple(gradient[1])) if gradient else None),
        )

    def font_for(self, field_name: str) -> Path:
        """The font file a given field draws with (its override, or the default)."""
        return self.fonts.get(field_name, self.font)


ELLIPSIS = "…"


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    field: Field,
    min_size: int,
    stroke_width: int = 0,
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Return the largest font, and the text, that fit the field's width.

    Shrinking beats overflowing: a long name spilling past the bar looks broken,
    a slightly smaller one does not. If even `min_size` will not fit, the text
    is truncated -- the renderer must never draw outside its box, whatever it
    is handed. The white outline widens every glyph by `stroke_width` on each
    side, so it is charged against the budget too.
    """
    budget = field.max_width - 2 * stroke_width

    size = field.font_size
    while size > min_size:
        font = load_font(font_path, size)
        if draw.textlength(text, font=font) <= budget:
            return font, text
        size -= 2

    font = load_font(font_path, min_size)
    if draw.textlength(text, font=font) <= budget:
        return font, text

    clipped = text
    while clipped and draw.textlength(clipped + ELLIPSIS, font=font) > budget:
        clipped = clipped[:-1]
    return font, clipped + ELLIPSIS


def _linear_gradient(
    size: tuple[int, int],
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> Image.Image:
    """A vertical `top`->`bottom` ramp, one row interpolated then stretched."""
    width, height = size
    column = Image.new("RGB", (1, height))
    pixels = column.load()
    span = max(height - 1, 1)
    for y in range(height):
        t = y / span
        pixels[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True))
    return column.resize((width, height))


def _draw_value(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    layout: Layout,
    anchor: str = "mm",
) -> None:
    """One value: a white outline, then a black->grey gradient poured into the glyphs.

    Pillow has no gradient fill, so the interior is a solid ramp image masked by
    the text shape. The outline is drawn straight onto the card first; the
    gradient sits inside it without a stroke of its own.
    """
    if layout.stroke_width:
        draw.text(
            xy,
            text,
            font=font,
            fill=layout.stroke_color,
            anchor=anchor,
            stroke_width=layout.stroke_width,
            stroke_fill=layout.stroke_color,
        )

    if layout.gradient is None:
        draw.text(xy, text, font=font, fill=layout.color, anchor=anchor)
        return

    left, top, right, bottom = draw.textbbox(xy, text, font=font, anchor=anchor)
    left, top = max(int(left), 0), max(int(top), 0)
    right = min(int(right) + 1, image.width)
    bottom = min(int(bottom) + 1, image.height)
    if right <= left or bottom <= top:
        return

    box_size = (right - left, bottom - top)
    mask = Image.new("L", box_size, 0)
    ImageDraw.Draw(mask).text((xy[0] - left, xy[1] - top), text, font=font, fill=255, anchor=anchor)
    ramp = _linear_gradient(box_size, layout.gradient[0], layout.gradient[1])
    image.paste(ramp, (left, top), mask)


def render(layout: Layout, values: dict[str, str]) -> BytesIO:
    """Draw `values` onto the template and return a PNG buffer.

    CPU-bound: async callers must wrap this in `asyncio.to_thread`.
    """
    image = Image.open(layout.template).convert("RGBA")
    draw = ImageDraw.Draw(image)

    for name, field in layout.fields.items():
        raw = values.get(name)
        if raw in (None, ""):
            continue
        font_path = str(layout.font_for(name))
        font, text = fit_text(
            draw, str(raw), font_path, field, layout.min_font_size, layout.stroke_width
        )
        # "mm" anchors on the middle of the glyph box in both axes, so a value
        # stays centred in its bar regardless of ascenders or descenders.
        _draw_value(image, draw, (field.x, field.y), text, font, layout, field.anchor)

    # Text is drawn at full template resolution and downscaled afterwards, so
    # glyph edges stay smooth. Telegram re-compresses photos anyway, so sending
    # the full 3080px original just costs upload time.
    if layout.output_width and layout.output_width < image.width:
        ratio = layout.output_width / image.width
        image = image.resize((layout.output_width, round(image.height * ratio)), Image.LANCZOS)

    buffer = BytesIO()
    # optimize=True costs seconds of CPU to save ~1% here -- a bad trade for a
    # per-request render.
    image.convert("RGB").save(buffer, format="PNG", compress_level=6)
    buffer.seek(0)
    return buffer
