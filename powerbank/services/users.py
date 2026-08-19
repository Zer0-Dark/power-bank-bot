"""User lifecycle. Pure business logic -- knows nothing about Telegram updates."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.db.models import User


@dataclass(frozen=True, slots=True)
class TelegramIdentity:
    """The subset of a Telegram user we persist.

    A plain dataclass rather than aiogram's `types.User` so this module stays
    free of framework imports and is trivial to construct in tests.
    """

    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    language_code: str | None = None


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create(session: AsyncSession, identity: TelegramIdentity) -> tuple[User, bool]:
    """Return (user, created). Refreshes the profile fields on every call.

    Telegram usernames and display names change often, so we keep ours current
    rather than trusting whatever was captured at registration.
    """
    user = await get_by_telegram_id(session, identity.telegram_id)
    created = False

    if user is None:
        user = User(telegram_id=identity.telegram_id)
        session.add(user)
        created = True

    user.username = identity.username
    user.first_name = identity.first_name
    user.language_code = identity.language_code
    user.last_seen_at = datetime.now(UTC)

    await session.flush()
    return user, created
