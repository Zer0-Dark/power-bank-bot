"""Power-pass card rendering.

Same shape as `test_render.py`'s per-tier account-card checks: every design
must have a loadable layout, a template that exists, a code field that sits
on the canvas, and must actually render a PNG with the code drawn onto it.
"""

from pathlib import Path

from PIL import Image

from powerbank.core.power_pass import PowerPassType, format_code
from powerbank.db.models import PowerPassCard
from powerbank.render.engine import render
from powerbank.render.power_pass import _layout, render_power_pass_sync

ASSETS = Path("assets")
LAYOUTS = {ct: _layout(str(ASSETS), ct) for ct in PowerPassType}


def pp_card(card_type: PowerPassType = PowerPassType.JOIN, n: int = 101) -> PowerPassCard:
    return PowerPassCard(card_type=card_type, code=format_code(card_type, n))


def test_every_type_has_a_loadable_layout_with_a_code_field():
    for card_type in PowerPassType:
        assert set(LAYOUTS[card_type].fields) == {"code"}


def test_every_type_has_an_existing_template():
    for card_type in PowerPassType:
        assert LAYOUTS[card_type].template.exists(), f"{card_type.value} template missing"


def test_every_type_field_sits_inside_its_template():
    for card_type in PowerPassType:
        layout = LAYOUTS[card_type]
        width, height = Image.open(layout.template).size
        field = layout.fields["code"]
        assert 0 < field.x < width, f"{card_type.value} x off-canvas"
        assert 0 < field.y < height, f"{card_type.value} y off-canvas"
        assert field.x + field.max_width // 2 <= width, f"{card_type.value} overflows right"
        assert field.x - field.max_width // 2 >= 0, f"{card_type.value} overflows left"


def test_every_type_renders_a_png_at_the_configured_output_width():
    for card_type in PowerPassType:
        layout = LAYOUTS[card_type]
        image = Image.open(render_power_pass_sync(pp_card(card_type), ASSETS))
        assert image.format == "PNG"
        assert image.width == layout.output_width


def test_the_code_actually_changes_the_pixels():
    """A blank render and a filled one must differ inside the code's box."""
    layout = LAYOUTS[PowerPassType.JOIN]
    field = layout.fields["code"]

    blank = Image.open(render(layout, {})).convert("L")
    filled = Image.open(render(layout, {"code": format_code(PowerPassType.JOIN, 101)})).convert("L")

    ratio = filled.width / Image.open(layout.template).width
    box = (
        int((field.x - 400) * ratio),
        int((field.y - 30) * ratio),
        int((field.x + 400) * ratio),
        int((field.y + 30) * ratio),
    )
    assert blank.crop(box).tobytes() != filled.crop(box).tobytes(), "nothing was drawn for code"


def test_different_codes_render_different_pixels():
    """Guards against a stale/cached layout silently reusing the same glyphs."""
    layout = LAYOUTS[PowerPassType.GOLD_72]
    a = Image.open(render(layout, {"code": format_code(PowerPassType.GOLD_72, 1)})).convert("L")
    b = Image.open(render(layout, {"code": format_code(PowerPassType.GOLD_72, 2)})).convert("L")
    assert a.tobytes() != b.tobytes()


def test_rendering_writes_nothing_to_disk(tmp_path, monkeypatch):
    """Same guarantee as the account-card renderer: in-memory only."""
    import os
    import tempfile

    assets = ASSETS.resolve()

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    def listing() -> set[str]:
        found = set()
        for root, _, files in os.walk(tmp_path):
            found |= {os.path.join(root, f) for f in files}
        return found

    before = listing()
    buffer = render_power_pass_sync(pp_card(), assets)
    assert len(buffer.getvalue()) > 0

    assert listing() == before, "the renderer left files behind"
