"""Opens one transactional DB session per update and injects it into handlers.

Outer middleware: it wraps filter evaluation too, so filters can query the DB.
The session commits when the handler returns normally and rolls back if it
raises -- handlers never call commit() themselves.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from powerbank.db.session import session_scope


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_scope(self.session_factory) as session:
            data["session"] = session
            return await handler(event, data)
