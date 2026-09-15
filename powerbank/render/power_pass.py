"""Rendering a power-pass card to a PNG.

Each power-pass design has its own template + layout under
``assets/layouts/power-pass`` keyed by the
:class:`~powerbank.core.power_pass.PowerPassType` value. Unlike an account
card's four typed fields, a power-pass card carries a single value: its code.
"""

import asyncio
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from powerbank.core.power_pass import PowerPassType
from powerbank.db.models import PowerPassCard
from powerbank.render.engine import Layout, render


@lru_cache(maxsize=len(PowerPassType))
def _layout(assets_dir: str, card_type: PowerPassType) -> Layout:
    """Parsed once per (assets dir, type) -- the JSON does not change at runtime."""
    root = Path(assets_dir)
    return Layout.load(root / "layouts" / "power-pass" / f"{card_type.value}.json", root)


def render_power_pass_sync(card: PowerPassCard, assets_dir: Path) -> BytesIO:
    return render(_layout(str(assets_dir), card.card_type), {"code": card.code})


async def render_power_pass(card: PowerPassCard, assets_dir: Path) -> BytesIO:
    """Render off the event loop.

    Pillow is CPU-bound; doing this inline would stall every other update while
    a multi-megapixel template is composited.
    """
    return await asyncio.to_thread(render_power_pass_sync, card, assets_dir)
