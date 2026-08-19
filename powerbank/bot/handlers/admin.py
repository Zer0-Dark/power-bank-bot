"""Membership management commands. Staff only.

Every handler here is gated by the IsStaff filter; the service layer
independently re-checks authority, so a filter mistake cannot escalate rights.
"""

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.bot.filters import IsStaff
from powerbank.core.exceptions import UserFacingError
from powerbank.core.roles import Role
from powerbank.db.models import User
from powerbank.services import access, users

router = Router(name="admin")
router.message.filter(IsStaff)

ROLE_WORDS = {
    "user": Role.USER,
    "u": Role.USER,
    "admin": Role.ADMIN,
    "a": Role.ADMIN,
}


async def _resolve_target(session: AsyncSession, query: str) -> int:
    """Turn an admin's argument into a Telegram id.

    A numeric id always works, even for someone the bot has never seen.
    A @username only resolves if they have messaged the bot before -- Telegram
    gives bots no way to look up a username otherwise.
    """
    text = query.strip()
    if text.lstrip("-").isdigit():
        return int(text)

    found = await users.get_by_username(session, text)
    if found is None:
        raise UserFacingError(
            f"I have never seen {text}. Ask them to message me once, "
            "then try again — or use their numeric ID."
        )
    return found.telegram_id


@router.message(Command("add"))
async def cmd_add(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    """/add <id|@username> [user|admin]"""
    args = (command.args or "").split()
    if not args:
        await message.answer(
            "Usage: <code>/add &lt;id|@username&gt; [user|admin]</code>\n"
            "Role defaults to <b>user</b>."
        )
        return

    role = ROLE_WORDS.get(args[1].lower()) if len(args) > 1 else Role.USER
    if role is None:
        await message.answer("Role must be <code>user</code> or <code>admin</code>.")
        return

    telegram_id = await _resolve_target(session, args[0])
    result = await access.grant_role(session, user, telegram_id, role)

    verb = "Added" if result.is_new_member else "Updated"
    await message.answer(
        f"✅ {verb} {hbold(result.user.display)} as {hbold(role.label)}\n<code>{telegram_id}</code>"
    )


@router.message(Command("remove"))
async def cmd_remove(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    """/remove <id|@username>"""
    if not command.args:
        await message.answer("Usage: <code>/remove &lt;id|@username&gt;</code>")
        return

    telegram_id = await _resolve_target(session, command.args)
    removed = await access.revoke_access(session, user, telegram_id)

    await message.answer(f"🗑 Removed {hbold(removed.display)}\n<code>{removed.telegram_id}</code>")


@router.message(Command("members"))
async def cmd_members(message: Message, session: AsyncSession) -> None:
    """/members — everyone with access, grouped by role."""
    members = await users.list_by_roles(session, (Role.SUPER_ADMIN, Role.ADMIN, Role.USER))
    if not members:
        await message.answer("No members yet.")
        return

    lines: list[str] = []
    current: Role | None = None
    for member in members:
        if member.role is not current:
            current = member.role
            lines.append(f"\n{hbold(current.label)}")
        lines.append(f"• {member.display} — <code>{member.telegram_id}</code>")

    await message.answer(f"{hbold('Members')} ({len(members)})\n" + "\n".join(lines))


@router.message(Command("who"))
async def cmd_who(message: Message, command: CommandObject, session: AsyncSession) -> None:
    """/who <id|@username> — look up anyone the bot has seen."""
    if not command.args:
        await message.answer("Usage: <code>/who &lt;id|@username&gt;</code>")
        return

    found = await users.resolve(session, command.args)
    if found is None:
        await message.answer("No record of that person.")
        return

    lines = [
        f"{hbold(found.display)}",
        f"ID: <code>{found.telegram_id}</code>",
        f"Role: {found.role.label}",
    ]
    if found.first_name:
        lines.append(f"Name: {found.first_name}")
    if found.last_seen_at:
        lines.append(f"Last seen: {found.last_seen_at:%Y-%m-%d %H:%M}")
    if found.denied_attempts:
        lines.append(f"Denied attempts: {found.denied_attempts}")
    if found.is_banned:
        lines.append("⚠️ Banned")

    await message.answer("\n".join(lines))


@router.message(Command("attempts"))
async def cmd_attempts(message: Message, session: AsyncSession) -> None:
    """/attempts — non-members who recently tried to get in."""
    knocking = await users.list_recent_denied(session)
    if not knocking:
        await message.answer("No access attempts recorded.")
        return

    lines = [
        f"• {u.display} — <code>{u.telegram_id}</code> "
        f"({u.denied_attempts} tries, last {u.last_denied_at:%m-%d %H:%M})"
        for u in knocking
    ]
    await message.answer(f"{hbold('Recent access attempts')}\n" + "\n".join(lines))
