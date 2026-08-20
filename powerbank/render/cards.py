"""Rendering an account card to a PNG."""

import asyncio
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from powerbank.db.models import Card
from powerbank.render.engine import Layout, render

LAYOUT_NAME = "account_card.json"


@lru_cache(maxsize=4)
def _layout(assets_dir: str) -> Layout:
    """Parsed once per process -- the JSON does not change at runtime."""
    root = Path(assets_dir)
    return Layout.load(root / "layouts" / LAYOUT_NAME, root)


def render_card_sync(card: Card, assets_dir: Path) -> BytesIO:
    return render(_layout(str(assets_dir)), card.as_values())


async def render_card(card: Card, assets_dir: Path) -> BytesIO:
    """Render off the event loop.

    Pillow is CPU-bound; doing this inline would stall every other update while
    a 3080x1993 template is composited.
    """
    return await asyncio.to_thread(render_card_sync, card, assets_dir)
