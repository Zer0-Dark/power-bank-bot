"""Rendering an account card to a PNG.

Each card tier has its own template + layout under ``assets/`` keyed by the
:class:`~powerbank.core.cards.CardType` value (``diamond`` ->
``layouts/diamond.json``). The card's ``card_type`` picks which one is drawn;
the four text values are the same across every design.
"""

import asyncio
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from powerbank.core.cards import CardType
from powerbank.db.models import Card
from powerbank.render.engine import Layout, render


@lru_cache(maxsize=len(CardType))
def _layout(assets_dir: str, card_type: CardType) -> Layout:
    """Parsed once per (assets dir, tier) -- the JSON does not change at runtime."""
    root = Path(assets_dir)
    return Layout.load(root / "layouts" / f"{card_type.value}.json", root)


def render_card_sync(card: Card, assets_dir: Path) -> BytesIO:
    return render(_layout(str(assets_dir), card.card_type), card.as_values())


async def render_card(card: Card, assets_dir: Path) -> BytesIO:
    """Render off the event loop.

    Pillow is CPU-bound; doing this inline would stall every other update while
    a multi-megapixel template is composited.
    """
    return await asyncio.to_thread(render_card_sync, card, assets_dir)
