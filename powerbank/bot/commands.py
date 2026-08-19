"""The native command menu Telegram shows behind the "/" button.

Scoped by role: admin commands are published only to the chats of people who
actually hold the role, so a plain user never sees commands they cannot use.
"""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.roles import Role
from powerbank.services.users import list_by_roles

log = logging.getLogger(__name__)

MEMBER_COMMANDS = [
    BotCommand(command="start", description="Main menu"),
    BotCommand(command="help", description="Show help"),
]

STAFF_COMMANDS = [
    *MEMBER_COMMANDS,
    BotCommand(command="members", description="List everyone with access"),
    BotCommand(command="add", description="Grant access to someone"),
    BotCommand(command="remove", description="Revoke someone's access"),
    BotCommand(command="who", description="Look someone up"),
    BotCommand(command="attempts", description="Who tried to get in"),
]


async def sync_for_user(bot: Bot, telegram_id: int, role: Role) -> None:
    """Publish the command list matching `role` to that person's private chat.

    Best-effort: someone who has never opened the bot has no chat to scope to,
    and that is not worth failing an admin action over.
    """
    commands = STAFF_COMMANDS if role.is_staff else MEMBER_COMMANDS
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=telegram_id))
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        log.debug("Could not set commands for %s: %s", telegram_id, exc)


async def setup_commands(bot: Bot, session: AsyncSession) -> None:
    """Called at startup: default list, plus the staff list for every admin."""
    await bot.set_my_commands(MEMBER_COMMANDS, scope=BotCommandScopeDefault())

    staff = await list_by_roles(session, (Role.SUPER_ADMIN, Role.ADMIN))
    for member in staff:
        await sync_for_user(bot, member.telegram_id, member.role)

    log.info("Command menu published (%s staff scoped)", len(staff))
