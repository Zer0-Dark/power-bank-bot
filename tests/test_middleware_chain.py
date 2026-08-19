"""Drives the real middleware chain with a synthetic update.

Verifies the contract handlers rely on: a committed session and a resolved
`user` kwarg, with no Telegram connection involved.
"""

import pytest_asyncio
from aiogram.types import Chat, Message, TelegramObject, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from powerbank.bot.middlewares.database import DatabaseMiddleware
from powerbank.bot.middlewares.user import UserMiddleware
from powerbank.db.models import Base, User
from powerbank.services.users import get_by_telegram_id

TG_USER = TgUser(id=555, is_bot=False, first_name="Abyss", username="abyss")


def make_update() -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=1,
            date=1_700_000_000,
            chat=Chat(id=555, type="private"),
            from_user=TG_USER,
            text="/start",
        ),
    )


@pytest_asyncio.fixture
async def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # StaticPool would be needed for a shared :memory: across connections;
    # a single connection per test is enough here.
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def run_chain(factory, data: dict) -> dict:
    """Run DatabaseMiddleware -> UserMiddleware and capture what a handler sees."""
    seen: dict = {}

    async def handler(event: TelegramObject, d: dict):
        seen.update(d)
        return None

    async def user_layer(event: TelegramObject, d: dict):
        return await UserMiddleware()(handler, event, d)

    update = make_update()
    await DatabaseMiddleware(factory)(user_layer, update, data)
    return seen


async def test_handler_receives_session_and_user(factory):
    seen = await run_chain(factory, {"event_from_user": TG_USER})

    assert "session" in seen
    assert isinstance(seen["user"], User)
    assert seen["user"].telegram_id == 555


async def test_user_is_committed_by_session_scope(factory):
    await run_chain(factory, {"event_from_user": TG_USER})

    # A fresh session must see the row -- proves the scope committed.
    async with factory() as check:
        assert await get_by_telegram_id(check, 555) is not None


async def test_banned_user_is_dropped_before_handler(factory):
    await run_chain(factory, {"event_from_user": TG_USER})
    async with factory() as s:
        user = await get_by_telegram_id(s, 555)
        user.is_banned = True
        await s.commit()

    seen = await run_chain(factory, {"event_from_user": TG_USER})
    assert seen == {}  # handler never ran


async def test_update_without_sender_passes_through(factory):
    seen = await run_chain(factory, {"event_from_user": None})

    assert "session" in seen
    assert "user" not in seen
