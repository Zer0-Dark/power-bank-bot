"""Screen text.

Commands and buttons render through the same functions, so the two entry points
cannot drift apart as features are added.
"""

from aiogram.utils.markdown import hbold

from powerbank.core.roles import Role
from powerbank.db.models import User

MEMBER_HELP = f"""{hbold("Power Bank — Help")}

Use the buttons below, or these commands:

/start — main menu
/help — this screen"""

STAFF_HELP = f"""

{hbold("Admin")}
/add &lt;id|@user&gt; [user|admin] — grant access
/remove &lt;id|@user&gt; — revoke access
/members — everyone with access
/who &lt;id|@user&gt; — look someone up
/attempts — who tried to get in

Every command above also has a button in the admin panel."""


def welcome(user: User) -> str:
    name = user.first_name or "there"
    return (
        f"Welcome to {hbold('Power Bank')}, {name}!\n"
        f"Signed in as {hbold(user.role.label)}.\n\n"
        "Pick an option below."
    )


def help_text(role: Role) -> str:
    return MEMBER_HELP + (STAFF_HELP if role.is_staff else "")


def admin_panel() -> str:
    return f"{hbold('Admin panel')}\n\nManage who can use the bot."


def members_list(members: list[User]) -> str:
    if not members:
        return "No members yet."

    lines: list[str] = []
    current: Role | None = None
    for member in members:
        if member.role is not current:
            current = member.role
            lines.append(f"\n{hbold(current.label)}")
        lines.append(f"• {member.display} — <code>{member.telegram_id}</code>")

    return f"{hbold('Members')} ({len(members)})\n" + "\n".join(lines)


def attempts_list(knocking: list[User]) -> str:
    if not knocking:
        return "No access attempts recorded."

    lines = [
        f"• {u.display} — <code>{u.telegram_id}</code> "
        f"({u.denied_attempts} tries, last {u.last_denied_at:%m-%d %H:%M})"
        for u in knocking
    ]
    return f"{hbold('Recent access attempts')}\n" + "\n".join(lines)


def profile(found: User) -> str:
    lines = [
        hbold(found.display),
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
    return "\n".join(lines)


def granted(user: User, role: Role, *, is_new: bool) -> str:
    verb = "Added" if is_new else "Updated"
    return (
        f"✅ {verb} {hbold(user.display)} as {hbold(role.label)}\n<code>{user.telegram_id}</code>"
    )


def removed(user: User) -> str:
    return f"🗑 Removed {hbold(user.display)}\n<code>{user.telegram_id}</code>"


ASK_TARGET_ADD = (
    "Who should I add?\n\n"
    "Send their <b>numeric ID</b>, or <b>@username</b> if they have messaged me before."
)
ASK_TARGET_REMOVE = "Who should I remove?\n\nSend their numeric ID or @username."
ASK_TARGET_WHO = "Who do you want to look up?\n\nSend a numeric ID or @username."
ASK_ROLE = "What role should they get?"
CANCELLED = "Cancelled."
