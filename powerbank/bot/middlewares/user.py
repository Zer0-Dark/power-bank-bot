"""Resolves the Telegram sender into our own User row and logs the contact.

Every sender is recorded, member or not -- that is what lets admins search for
someone by @username later, and gives us a record of who tried to get in.
Recording grants no access; that decision belongs to AccessMiddleware.

Runs after DatabaseMiddleware, so `data["session"]` is already present.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TgUser

from powerbank.services.users import TelegramIdentity, record_contact

log = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")

        # Channel posts and similar updates have no sender; let them through
        # untouched rather than inventing a user for them.
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        user = await record_contact(
            data["session"],
            TelegramIdentity(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                language_code=tg_user.language_code,
            ),
        )

        data["user"] = user
        return await handler(event, data)
