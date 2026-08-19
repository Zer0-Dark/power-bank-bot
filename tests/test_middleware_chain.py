"""Drives the real middleware chain with a synthetic update.

Verifies the contract handlers rely on: a committed session, a resolved `user`,
and -- critically -- that non-members never reach a handler. No Telegram
connection involved; replies are captured by a stub.
"""

import pytest_asyncio
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from powerbank.bot.callbacks import Nav, NavCb
from powerbank.bot.middlewares.access import AccessMiddleware
from powerbank.bot.middlewares.database import DatabaseMiddleware
from powerbank.bot.middlewares.user import UserMiddleware
from powerbank.core.roles import Role
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


async def run_chain(factory, data: dict, *, replies: list | None = None) -> dict:
    """Run database -> user -> access, capturing what a handler would see."""
    seen: dict = {}

    async def handler(event: TelegramObject, d: dict):
        seen.update(d)
        return None

    async def access_layer(event: TelegramObject, d: dict):
        return await AccessMiddleware()(handler, event, d)

    async def user_layer(event: TelegramObject, d: dict):
        return await UserMiddleware()(access_layer, event, d)

    sink = replies if replies is not None else []
    update = make_update()

    # Intercept replies instead of hitting the network. Always installed: the
    # deny path calls answer() whether or not a test inspects the text.
    async def answer(text: str, **kw):
        sink.append(text)

    object.__setattr__(update.message, "answer", answer)

    await DatabaseMiddleware(factory)(user_layer, update, data)
    return seen


async def grant(factory, telegram_id: int, role: Role) -> None:
    """Mirror what access.grant_role does, without needing an actor row.

    Clearing the deny record matters: a cooldown left over from before someone
    was a member would otherwise silence a later, legitimate denial.
    """
    async with factory() as s:
        user = await get_by_telegram_id(s, telegram_id)
        user.role = role
        if role.is_member:
            user.denied_attempts = 0
            user.last_denied_at = None
        await s.commit()


async def test_member_reaches_the_handler(factory):
    await run_chain(factory, {"event_from_user": TG_USER})  # records contact
    await grant(factory, 555, Role.USER)

    seen = await run_chain(factory, {"event_from_user": TG_USER})

    assert "session" in seen
    assert isinstance(seen["user"], User)
    assert seen["user"].role is Role.USER


async def test_unknown_sender_is_recorded_but_denied(factory):
    replies: list[str] = []
    seen = await run_chain(factory, {"event_from_user": TG_USER}, replies=replies)

    assert seen == {}, "handler must not run for a non-member"

    async with factory() as s:
        user = await get_by_telegram_id(s, 555)
        assert user is not None, "contact must still be logged for admin search"
        assert user.role is Role.NONE
        assert user.denied_attempts == 1

    assert len(replies) == 1
    assert "بالدعوة فقط" in replies[0]
    assert "555" in replies[0], "the denial must show their id so they can share it"


async def test_repeat_attempts_count_but_reply_is_throttled(factory):
    replies: list[str] = []
    for _ in range(3):
        await run_chain(factory, {"event_from_user": TG_USER}, replies=replies)

    async with factory() as s:
        user = await get_by_telegram_id(s, 555)
        assert user.denied_attempts == 3, "every attempt is recorded"

    assert len(replies) == 1, "but the bot replies once per cooldown window"


async def test_banned_member_is_denied(factory):
    await run_chain(factory, {"event_from_user": TG_USER})
    await grant(factory, 555, Role.USER)
    async with factory() as s:
        user = await get_by_telegram_id(s, 555)
        user.is_banned = True
        await s.commit()

    replies: list[str] = []
    seen = await run_chain(factory, {"event_from_user": TG_USER}, replies=replies)

    assert seen == {}
    assert "تم سحب صلاحيتك" in replies[0]


async def test_revoked_member_loses_access_immediately(factory):
    await run_chain(factory, {"event_from_user": TG_USER})
    await grant(factory, 555, Role.USER)
    assert await run_chain(factory, {"event_from_user": TG_USER}) != {}

    await grant(factory, 555, Role.NONE)

    assert await run_chain(factory, {"event_from_user": TG_USER}) == {}


async def test_contact_is_committed(factory):
    await run_chain(factory, {"event_from_user": TG_USER})

    # A fresh session must see the row -- proves the scope committed.
    async with factory() as check:
        assert await get_by_telegram_id(check, 555) is not None


async def test_update_without_sender_passes_through(factory):
    seen = await run_chain(factory, {"event_from_user": None})

    assert "session" in seen
    assert "user" not in seen


# --- the gate covers buttons, not just commands ---


def make_callback_update() -> Update:
    """A button press from the same user."""
    return Update(
        update_id=2,
        callback_query=CallbackQuery(
            id="cb1",
            from_user=TG_USER,
            chat_instance="ci",
            data=NavCb(to=Nav.ADMIN).pack(),
            message=Message(
                message_id=2,
                date=1_700_000_000,
                chat=Chat(id=555, type="private"),
                from_user=TG_USER,
                text="menu",
            ),
        ),
    )


async def run_callback_chain(factory, toasts: list[str]) -> dict:
    seen: dict = {}

    async def handler(event: TelegramObject, d: dict):
        seen.update(d)
        return None

    async def access_layer(event: TelegramObject, d: dict):
        return await AccessMiddleware()(handler, event, d)

    async def user_layer(event: TelegramObject, d: dict):
        return await UserMiddleware()(access_layer, event, d)

    update = make_callback_update()

    async def answer(text: str = "", **kw):
        toasts.append(text)

    object.__setattr__(update.callback_query, "answer", answer)

    await DatabaseMiddleware(factory)(user_layer, update, {"event_from_user": TG_USER})
    return seen


async def test_non_member_pressing_a_button_is_denied(factory):
    toasts: list[str] = []

    seen = await run_callback_chain(factory, toasts)

    assert seen == {}, "a stale button must not bypass the gate"
    assert toasts, "an unanswered callback leaves the client spinning forever"
    assert "بالدعوة فقط" in toasts[0]


async def test_button_denial_is_never_throttled(factory):
    toasts: list[str] = []
    for _ in range(3):
        await run_callback_chain(factory, toasts)

    # A toast is not a new message, so answering every time cannot spam anyone
    # -- and staying silent would hang their client.
    assert len(toasts) == 3


async def test_member_pressing_a_button_reaches_the_handler(factory):
    await run_callback_chain(factory, [])
    await grant(factory, 555, Role.USER)

    seen = await run_callback_chain(factory, [])

    assert seen.get("user") is not None
