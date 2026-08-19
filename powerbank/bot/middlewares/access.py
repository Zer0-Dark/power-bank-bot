"""The access gate. Nothing past this point runs for a non-member.

Placed after UserMiddleware so the sender is already resolved and logged.
Handlers can therefore assume `user.has_access` is true and never check it.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update

from powerbank.db.models import User
from powerbank.services.users import record_denied_attempt

log = logging.getLogger(__name__)

DENIED_TEXT = (
    "🔒 <b>Power Bank</b> is invite-only.\n\n"
    "Ask an admin to add you. Give them your ID:\n<code>{telegram_id}</code>"
)

BANNED_TEXT = "🚫 Your access to Power Bank has been revoked."

# A non-member who keeps messaging gets one reply per window, not one per
# message -- otherwise the bot happily amplifies anyone spamming it.
DENY_REPLY_COOLDOWN = timedelta(minutes=5)


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("user")

        # No resolved sender (channel post, etc.) -- nothing to gate.
        if user is None:
            return await handler(event, data)

        if user.has_access:
            return await handler(event, data)

        last_denied = user.last_denied_at
        await record_denied_attempt(data["session"], user)
        log.info(
            "Denied access: tg=%s @%s attempts=%s",
            user.telegram_id,
            user.username,
            user.denied_attempts,
        )

        message = _extract_message(event)
        if message is not None and _should_reply(last_denied):
            text = BANNED_TEXT if user.is_banned else DENIED_TEXT
            await message.answer(text.format(telegram_id=user.telegram_id))

        return None  # handler chain stops here


def _should_reply(last_denied_at: datetime | None) -> bool:
    if last_denied_at is None:
        return True
    if last_denied_at.tzinfo is None:  # SQLite returns naive datetimes
        last_denied_at = last_denied_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_denied_at > DENY_REPLY_COOLDOWN


def _extract_message(event: TelegramObject) -> Message | None:
    if isinstance(event, Update):
        return event.message or (event.callback_query.message if event.callback_query else None)
    if isinstance(event, Message):
        return event
    return None
