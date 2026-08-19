"""User lifecycle and lookup. Pure business logic -- no Telegram imports."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.roles import Role
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


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    """Case-insensitive username lookup. Only finds people the bot has seen."""
    handle = username.lstrip("@")
    return await session.scalar(select(User).where(func.lower(User.username) == handle.lower()))


async def resolve(session: AsyncSession, query: str) -> User | None:
    """Find a user by numeric id or @username -- whichever the admin typed."""
    text = query.strip()
    if text.lstrip("-").isdigit():
        return await get_by_telegram_id(session, int(text))
    return await get_by_username(session, text)


async def record_contact(session: AsyncSession, identity: TelegramIdentity) -> User:
    """Log that we saw this person, creating the row if it is new.

    Called for EVERY incoming update, member or not. Creating a row grants no
    access -- new rows default to Role.NONE. This is what makes it possible for
    an admin to later search for someone by username.

    Profile fields are refreshed each time, since Telegram usernames and display
    names change often and stale ones make admin search fail.
    """
    user = await get_by_telegram_id(session, identity.telegram_id)

    if user is None:
        user = User(telegram_id=identity.telegram_id, role=Role.NONE)
        session.add(user)

    user.username = identity.username
    user.first_name = identity.first_name
    user.language_code = identity.language_code
    user.last_seen_at = datetime.now(UTC)

    await session.flush()
    return user


async def record_denied_attempt(session: AsyncSession, user: User) -> None:
    """Note that a non-member tried to use the bot."""
    user.denied_attempts += 1
    user.last_denied_at = datetime.now(UTC)
    await session.flush()


def _seniority():
    """Order by rank, not by the stored string.

    `role` is a VARCHAR, so ORDER BY role sorts alphabetically -- which puts
    'user' above 'super_admin'. Map to the numeric rank instead.
    """
    return case({role.value: role.rank for role in Role}, value=User.role, else_=0)


async def list_by_roles(session: AsyncSession, roles: tuple[Role, ...]) -> list[User]:
    result = await session.scalars(
        select(User).where(User.role.in_(roles)).order_by(_seniority().desc(), User.id)
    )
    return list(result)


async def list_recent_denied(session: AsyncSession, limit: int = 15) -> list[User]:
    """Non-members who recently tried to get in, most recent first."""
    result = await session.scalars(
        select(User)
        .where(User.denied_attempts > 0, User.role == Role.NONE)
        .order_by(User.last_denied_at.desc())
        .limit(limit)
    )
    return list(result)
