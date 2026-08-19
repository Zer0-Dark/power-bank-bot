"""Rendering a screen, from either a command or a button press.

A command sends a new message; a button edits the one already on screen. Both
go through `show()` so handlers never care which triggered them.
"""

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


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
        # Re-rendering an identical screen is not an error worth surfacing.
        if "message is not modified" not in str(exc):
            raise
