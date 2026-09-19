from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from powerbank.core.config import get_settings
from powerbank.db.models import Base

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """A fresh in-memory database per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    """Alembic pointed at a throwaway SQLite file, for walking the migration chain."""
    db = tmp_path / "mig.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    get_settings.cache_clear()  # env.py reads get_settings() at import
    monkeypatch.chdir(PROJECT_ROOT)
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    yield cfg, db
    get_settings.cache_clear()
