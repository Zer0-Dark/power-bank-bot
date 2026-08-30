"""Rendering a screen, from either a command or a button press.

A command sends a new message; a button edits the one already on screen. Both
go through `show()` so handlers never care which triggered them.
"""

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)

from powerbank.core.config import Settings
from powerbank.render.cards import render_card


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
