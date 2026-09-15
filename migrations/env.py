"""Alembic environment, wired to our async engine and Settings."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from powerbank.core.config import get_settings
from powerbank.db.models import Base  # imports every model for autogenerate

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
DATABASE_URL = get_settings().database_url


# Autogenerate plugins to run. The check-constraint comparator is excluded:
# SQLAlchemy emits a CHECK for every `Enum(create_constraint=True)` column, but
# autogenerate cannot match the reflected constraint back to the model, so on
# *every* migration it proposes dropping and recreating them. That already cost
# us the role constraint once -- an unnoticed `upgrade` silently removed a real
# data guarantee. Check constraints are authored by hand instead.
AUTOGENERATE_PLUGINS = [
    "alembic.autogenerate.*",
    "~alembic.autogenerate.checkconstraint_byname",
]


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        autogenerate_plugins=AUTOGENERATE_PLUGINS,
        # SQLite cannot ALTER columns in place; batch mode rewrites the table.
        render_as_batch=DATABASE_URL.startswith("sqlite"),
    )


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # `.begin()`, not `.connect()`: SQLAlchemy 2.0 connections autobegin but
    # never autocommit, so a plain `.connect()` here silently rolls every
    # migration back on close. Postgres's transactional DDL makes that
    # obvious; SQLite masked it, since its DDL effectively autocommits.
    engine = create_async_engine(DATABASE_URL, poolclass=None)
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: (_configure(c), context.run_migrations()))
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
