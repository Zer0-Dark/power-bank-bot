"""Catch-all error handler.

Domain errors carry a message we can show the user. Anything else is a bug:
log it with a traceback and give the user a neutral apology, never internals.
"""

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from powerbank.core.exceptions import PowerBankError

log = logging.getLogger(__name__)

router = Router(name="errors")


@router.error()
async def on_error(event: ErrorEvent) -> bool:
    exception = event.exception
    message = getattr(event.update, "message", None)

    if isinstance(exception, PowerBankError):
        log.info("Domain error: %s", exception)
        if message is not None:
            await message.answer(exception.user_message)
        return True

    log.exception("Unhandled error while processing update", exc_info=exception)
    if message is not None:
        await message.answer("Something went wrong on our side. Please try again.")
    return True
