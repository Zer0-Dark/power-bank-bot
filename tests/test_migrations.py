"""The migration chain actually runs.

conftest builds the schema with `Base.metadata.create_all`, so nothing else here
exercises the Alembic revisions. This walks the chain end to end against a
throwaway SQLite file and checks the card rework's backfill.
"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from powerbank.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CARD_REWORK = "c977b6426465"
CARD_REWORK_PARENT = "8c35e4f3106d"


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    db = tmp_path / "mig.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db}")
    get_settings.cache_clear()  # env.py reads get_settings() at import
    monkeypatch.chdir(PROJECT_ROOT)
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    yield cfg, db
    get_settings.cache_clear()


def _columns(db, table) -> set[str]:
    con = sqlite3.connect(db)
    try:
        return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def test_full_chain_upgrades_from_empty(alembic_cfg):
    cfg, db = alembic_cfg
    command.upgrade(cfg, "head")
    assert "created_by_id" in _columns(db, "cards")
    assert "user_id" not in _columns(db, "cards")


def test_card_rework_backfills_created_by_from_the_former_owner(alembic_cfg):
    cfg, db = alembic_cfg
    command.upgrade(cfg, CARD_REWORK_PARENT)

    con = sqlite3.connect(db)
    con.execute("INSERT INTO users (id, telegram_id, is_banned, role) VALUES (1, 42, 0, 'user')")
    con.execute(
        "INSERT INTO cards (id, user_id, bank_number, real_name, facebook_name, display_username) "
        "VALUES (1, 1, 76, 'x', 'x', 'x')"
    )
    con.commit()
    con.close()

    command.upgrade(cfg, "head")

    con = sqlite3.connect(db)
    try:
        row = con.execute("SELECT created_by_id FROM cards WHERE id = 1").fetchone()
    finally:
        con.close()
    assert row == (1,)


def test_card_rework_downgrades(alembic_cfg):
    cfg, _ = alembic_cfg
    command.upgrade(cfg, "head")
    command.downgrade(cfg, CARD_REWORK_PARENT)
    command.upgrade(cfg, "head")
