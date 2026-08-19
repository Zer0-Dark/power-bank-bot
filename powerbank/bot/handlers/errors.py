"""Catch-all error handler.

Domain errors carry a message we can show the user. Anything else is a bug:
log it with a traceback and give the user a neutral apology, never internals.
"""

import logging

from aiogram import Router
from aiogram.types import CallbackQuery, ErrorEvent, Message, Update

from powerbank.core.exceptions import PowerBankError

log = logging.getLogger(__name__)

router = Router(name="errors")


def _reply_target(update: Update) -> Message | CallbackQuery | None:
    """Where to put the apology -- a button press has no message of its own."""
    if update.message is not None:
        return update.message
    if update.callback_query is not None:
        return update.callback_query
    return None


async def _tell(target: Message | CallbackQuery, text: str) -> None:
    if isinstance(target, CallbackQuery):
        # Shown as a toast, so the screen the user was on stays intact.
        await target.answer(text, show_alert=True)
    else:
        await target.answer(text)


@router.error()
async def on_error(event: ErrorEvent) -> bool:
    exception = event.exception
    target = _reply_target(event.update)

    if isinstance(exception, PowerBankError):
        log.info("Domain error: %s", exception)
        if target is not None:
            await _tell(target, exception.user_message)
        return True

    log.exception("Unhandled error while processing update", exc_info=exception)
    if target is not None:
        await _tell(target, "Something went wrong on our side. Please try again.")
    return True
