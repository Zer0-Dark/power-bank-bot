"""Rendering a screen, from either a command or a button press.

A command sends a new message; a button edits the one already on screen. Both
go through `show()` so handlers never care which triggered them.
"""

import asyncio
from collections.abc import Awaitable, Callable
from io import BytesIO
from pathlib import Path
from typing import Protocol

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)

from powerbank.core.config import Settings
from powerbank.render.cards import render_card


class _HasCode(Protocol):
    code: str


async def show(
    event: Message | CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard)
        return

    await event.answer()  # stop the client's loading spinner

    if event.message is None:  # too old for Telegram to give us the message
        return

    try:
        await event.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        detail = str(exc)
        # Re-rendering an identical screen is not an error worth surfacing.
        if "message is not modified" in detail:
            return
        # The button was attached to a photo (a rendered card): a text screen
        # cannot replace it in place, so send a fresh one.
        if "no text in the message to edit" in detail or "message can't be edited" in detail:
            await event.message.answer(text, reply_markup=keyboard)
            return
        raise


async def send_card_image(
    event: Message | CallbackQuery,
    card,
    settings: Settings,
    *,
    caption: str | None = None,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Render a card to a PNG and deliver it as a photo.

    Always a new message -- a photo cannot replace a text screen in place.
    """
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    buffer = await render_card(card, settings.assets_dir)
    await message.answer_photo(
        BufferedInputFile(buffer.getvalue(), filename=f"{card.formatted_number}.png"),
        caption=caption,
        reply_markup=keyboard,
    )


async def send_code_card_batch(
    event: Message | CallbackQuery,
    batch: list[_HasCode],
    render: Callable[[_HasCode, Path], Awaitable[BytesIO]],
    assets_dir: Path,
    *,
    caption: str | None = None,
    keyboard: InlineKeyboardMarkup | None = None,
) -> None:
    """Render a batch to PNGs and deliver each as its own photo message.

    Shared by power-pass, coins and store cards: all mint owner-less, code-only cards
    from a batch, differing only in how a single item renders. One message
    per card -- not a media-group album -- so each code is fully visible and
    legible on its own, not shrunk into an album thumbnail grid.
    """
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    if caption:
        await message.answer(caption)

    buffers = await asyncio.gather(*(render(card, assets_dir) for card in batch))
    for card, buf in zip(batch, buffers, strict=True):
        await message.answer_photo(
            BufferedInputFile(buf.getvalue(), filename=f"{card.code}.png"),
            caption=card.code,
        )

    if keyboard is not None:
        await message.answer("✅ تم", reply_markup=keyboard)
