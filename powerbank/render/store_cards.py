"""Rendering a store card to a PNG.

Each type has its own template + layout under ``assets/layouts/store-cards``
keyed by the :class:`~powerbank.core.store_cards.StoreCardType` value. Like a
coin note, a store card carries a single value: its code.
"""

import asyncio
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from powerbank.core.store_cards import StoreCardType
from powerbank.db.models import StoreCard
from powerbank.render.engine import Layout, render


@lru_cache(maxsize=len(StoreCardType))
def _layout(assets_dir: str, card_type: StoreCardType) -> Layout:
    """Parsed once per (assets dir, type) -- the JSON does not change at runtime."""
    root = Path(assets_dir)
    return Layout.load(root / "layouts" / "store-cards" / f"{card_type.value}.json", root)


def render_store_card_sync(card: StoreCard, assets_dir: Path) -> BytesIO:
    return render(_layout(str(assets_dir), card.card_type), {"code": card.code})


async def render_store_card(card: StoreCard, assets_dir: Path) -> BytesIO:
    """Render off the event loop -- Pillow is CPU-bound."""
    return await asyncio.to_thread(render_store_card_sync, card, assets_dir)
