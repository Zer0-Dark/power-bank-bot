"""Rendering a coin note to a PNG.

Each denomination has its own template + layout under ``assets/layouts/coins``
keyed by the :class:`~powerbank.core.coins.CoinType` value. Like a power-pass
card, a coin note carries a single value: its code.
"""

import asyncio
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from powerbank.core.coins import CoinType
from powerbank.db.models import CoinCard
from powerbank.render.engine import Layout, render


@lru_cache(maxsize=len(CoinType))
def _layout(assets_dir: str, coin_type: CoinType) -> Layout:
    """Parsed once per (assets dir, type) -- the JSON does not change at runtime."""
    root = Path(assets_dir)
    return Layout.load(root / "layouts" / "coins" / f"{coin_type.value}.json", root)


def render_coin_sync(card: CoinCard, assets_dir: Path) -> BytesIO:
    return render(_layout(str(assets_dir), card.coin_type), {"code": card.code})


async def render_coin(card: CoinCard, assets_dir: Path) -> BytesIO:
    """Render off the event loop.

    Pillow is CPU-bound; doing this inline would stall every other update while
    a multi-megapixel template is composited.
    """
    return await asyncio.to_thread(render_coin_sync, card, assets_dir)
