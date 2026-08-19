"""Entrypoint: `python -m powerbank`."""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from powerbank.bot.commands import setup_commands
from powerbank.bot.factory import create_bot, create_dispatcher
from powerbank.core.config import get_settings
from powerbank.core.logging import setup_logging
from powerbank.db.session import create_engine, create_session_factory, session_scope
from powerbank.services.access import sync_super_admins

log = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    bot: Bot = create_bot(settings)
    dp: Dispatcher = create_dispatcher(settings, session_factory)

    async with session_scope(session_factory) as session:
        seeded = await sync_super_admins(session, settings.super_admin_ids)
    if seeded:
        log.info("Seeded super admins: %s", [u.telegram_id for u in seeded])
    elif not settings.super_admin_ids:
        log.warning(
            "SUPER_ADMIN_IDS is empty -- nobody can administer this bot. "
            "Set it in .env and restart."
        )

    try:
        me = await bot.get_me()
        log.info("Starting @%s (env=%s)", me.username, settings.environment)

        async with session_scope(session_factory) as session:
            await setup_commands(bot, session)

        # Drop updates that queued while we were down; on restart they are
        # almost always stale and replaying them confuses users.
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        log.info("Shutting down")
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        log.info("Stopped by signal")


if __name__ == "__main__":
    main()
