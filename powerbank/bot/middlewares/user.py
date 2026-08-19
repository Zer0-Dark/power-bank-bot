"""Resolves the Telegram sender into our own User row.

Runs after DatabaseMiddleware, so `data["session"]` is already present.
Handlers receive a ready `user` and never do lookup themselves.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TgUser

from powerbank.services.users import TelegramIdentity, get_or_create

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

        user, created = await get_or_create(
            data["session"],
            TelegramIdentity(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                language_code=tg_user.language_code,
            ),
        )

        if created:
            log.info("Registered new user tg=%s @%s", tg_user.id, tg_user.username)

        # Banned users are dropped here so no handler has to check.
        if user.is_banned:
            log.info("Ignoring update from banned user tg=%s", tg_user.id)
            return None

        data["user"] = user
        return await handler(event, data)
