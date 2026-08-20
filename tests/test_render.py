"""Card rendering.

The bug worth guarding here is silent: Arabic that fails to shape renders as
tofu boxes rather than raising, so a broken card looks fine to the code and
wrong to the user. These tests check the pixels, not just that no exception
was raised.
"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from powerbank.db.models import Card
from powerbank.render.cards import render_card_sync
from powerbank.render.engine import Layout, fit_text, load_font, render, require_shaping

ASSETS = Path("assets")
LAYOUT = Layout.load(ASSETS / "layouts" / "account_card.json", ASSETS)

ARABIC = "سجاد عدي الفهد"


def card(**overrides) -> Card:
    base = {
        "real_name": ARABIC,
        "facebook_name": ARABIC,
        "bank_number": 76,
        "display_username": "MusaGRO",
    }
    return Card(**(base | overrides))


def test_shaping_is_available():
    # If this fails, every card renders as tofu -- fail here, loudly, not there.
    require_shaping()


def test_arabic_shapes_to_connected_glyphs():
    """Unshaped Arabic is wider than shaped: letters do not join.

    A cheap, robust proxy for "shaping actually ran" that does not depend on
    exact font metrics.
    """
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font_path = str(LAYOUT.font)

    shaped = draw.textlength(ARABIC, font=load_font(font_path, 88))
    isolated = draw.textlength(
        ARABIC,
        font=ImageFont.truetype(font_path, 88, layout_engine=ImageFont.Layout.BASIC),
    )
    assert shaped < isolated


def test_font_covers_every_script_the_card_uses():
    """Arabic names, a Latin username and digits share one font face."""
    from fontTools.ttLib import TTFont

    font = TTFont(str(LAYOUT.font), fontNumber=0)
    covered = set()
    for table in font["cmap"].tables:
        covered |= set(table.cmap.keys())

    for sample in (ARABIC.replace(" ", ""), "MusaGRO", "0123456789"):
        missing = [c for c in sample if ord(c) not in covered]
        assert not missing, f"font is missing {missing}"


def test_renders_a_png_at_the_configured_output_width():
    buffer = render_card_sync(card(), ASSETS)

    image = Image.open(buffer)
    assert image.format == "PNG"
    assert image.width == LAYOUT.output_width

    # Aspect ratio must survive the downscale.
    template = Image.open(LAYOUT.template)
    assert abs(image.width / image.height - template.width / template.height) < 0.01


def scaled_box(field, image) -> tuple[int, int, int, int]:
    """A field's box in output pixels, after the render's downscale."""
    ratio = image.width / Image.open(LAYOUT.template).width
    return (
        int((field.x - 200) * ratio),
        int((field.y - 30) * ratio),
        int((field.x + 200) * ratio),
        int((field.y + 30) * ratio),
    )


def test_values_actually_change_the_pixels():
    """A blank render and a filled one must differ inside the value boxes."""
    blank = Image.open(render(LAYOUT, {})).convert("L")
    filled = Image.open(render_card_sync(card(), ASSETS)).convert("L")

    for name, field in LAYOUT.fields.items():
        box = scaled_box(field, filled)
        assert blank.crop(box).tobytes() != filled.crop(box).tobytes(), (
            f"nothing was drawn for {name}"
        )


def test_no_tofu_boxes_are_drawn():
    """The bug this guards is silent: unshapable text draws boxes, not an error.

    U+FE8D is an Arabic Presentation Form -- exactly what `arabic-reshaper`
    emits, and exactly what Readex Pro does not contain. Rendering it produces
    tofu. If real Arabic produced the same pixels, shaping is broken.
    """
    real = Image.open(render(LAYOUT, {"real_name": ARABIC})).convert("L")
    tofu = Image.open(render(LAYOUT, {"real_name": "\ufe8d" * 6})).convert("L")

    box = scaled_box(LAYOUT.fields["real_name"], real)
    assert real.crop(box).tobytes() != tofu.crop(box).tobytes()


@pytest.mark.parametrize(
    "value",
    [
        "عبد الرحمن",
        "عبد الرحمن بن عبد العزيز بن محمد",
        "عبد الرحمن بن عبد العزيز بن محمد الطويل جداً وأطول",
        "W" * 80,
    ],
)
def test_text_never_overflows_its_box(value: str):
    """Whatever it is handed, the renderer stays inside the bar."""
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    field = LAYOUT.fields["real_name"]

    font, drawn = fit_text(draw, value, str(LAYOUT.font), field, LAYOUT.min_font_size)

    assert draw.textlength(drawn, font=font) <= field.max_width


def test_untruncatable_text_is_ellipsised_not_clipped():
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    _, drawn = fit_text(
        draw, "W" * 80, str(LAYOUT.font), LAYOUT.fields["real_name"], LAYOUT.min_font_size
    )

    assert drawn.endswith("…"), "silent clipping hides that a value was cut"


def test_blank_values_leave_the_bar_untouched():
    """A missing value must draw nothing -- not "None", not an empty box."""
    blank = Image.open(render(LAYOUT, {})).convert("L")
    empties = Image.open(render(LAYOUT, {"real_name": "", "username": None})).convert("L")

    for field in LAYOUT.fields.values():
        box = scaled_box(field, blank)
        assert blank.crop(box).tobytes() == empties.crop(box).tobytes()


def test_layout_fields_are_inside_the_template():
    template = Image.open(LAYOUT.template)
    width, height = template.size

    for name, field in LAYOUT.fields.items():
        assert 0 < field.x < width, f"{name} x is off-canvas"
        assert 0 < field.y < height, f"{name} y is off-canvas"
        assert field.x + field.max_width // 2 <= width, f"{name} overflows the right edge"


@pytest.mark.parametrize("value", ["MusaGRO", "١٢٣", "00000076", "أ ب ج"])
def test_mixed_scripts_render_without_error(value):
    render(LAYOUT, {"username": value})


# --- no junk on disk -----------------------------------------------------


def test_rendering_writes_nothing_to_disk(tmp_path, monkeypatch):
    """Cards exist in memory only, from render to upload.

    Guards against a future change that "optimises" rendering by writing a
    temp file -- which would leave a 1.5MB PNG per card on the server.
    """
    import os
    import tempfile

    # Resolve assets *before* chdir, or the relative path follows us.
    assets = ASSETS.resolve()

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    def listing() -> set[str]:
        found = set()
        for root, _, files in os.walk(tmp_path):
            found |= {os.path.join(root, f) for f in files}
        return found

    before = listing()
    buffer = render_card_sync(card(), assets)
    assert len(buffer.getvalue()) > 0

    assert listing() == before, "the renderer left files behind"


def test_render_returns_an_in_memory_buffer():
    from io import BytesIO

    assert isinstance(render_card_sync(card(), ASSETS), BytesIO)


def test_buffer_is_released_once_dropped():
    import gc
    import weakref

    buffer = render_card_sync(card(), ASSETS)
    ref = weakref.ref(buffer)

    del buffer
    gc.collect()

    assert ref() is None, "a retained buffer means 1.5MB leaked per card"
