"""Engine and session factory.

One engine per process, created at startup and disposed at shutdown.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from powerbank.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    kwargs: dict = {"echo": settings.db_echo}
    if not settings.is_sqlite:
        # Modest pool: a single bot process does not need many connections,
        # and Telegram rate limits cap our real concurrency anyway.
        kwargs |= {"pool_size": 10, "max_overflow": 5, "pool_pre_ping": True}
    return create_async_engine(settings.database_url, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,  # objects stay usable after commit, inside handlers
        autoflush=False,
    )


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Transactional scope: commit on success, roll back on any exception."""
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
