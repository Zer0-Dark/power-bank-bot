"""Wiring. The single place where every layer is connected together."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from powerbank.bot.handlers import build_router
from powerbank.bot.middlewares.database import DatabaseMiddleware
from powerbank.bot.middlewares.user import UserMiddleware
from powerbank.core.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    # MemoryStorage is fine while we run a single process. Swap to RedisStorage
    # when we scale out or want FSM state to survive restarts.
    dp = Dispatcher(storage=MemoryStorage())

    # Available to every handler via the `settings` kwarg.
    dp["settings"] = settings

    # Outer middlewares run before filters, so filters can use the session and
    # the resolved user. Order is significant: user lookup needs the session.
    dp.update.outer_middleware(DatabaseMiddleware(session_factory))
    dp.update.outer_middleware(UserMiddleware())

    dp.include_router(build_router())
    return dp
