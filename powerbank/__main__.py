"""Entrypoint: `python -m powerbank`."""

import asyncio
import logging

from aiogram import Bot, Dispatcher

from powerbank.bot.factory import create_bot, create_dispatcher
from powerbank.core.config import get_settings
from powerbank.core.logging import setup_logging
from powerbank.db.session import create_engine, create_session_factory

log = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    bot: Bot = create_bot(settings)
    dp: Dispatcher = create_dispatcher(settings, session_factory)

    try:
        me = await bot.get_me()
        log.info("Starting @%s (env=%s)", me.username, settings.environment)

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
