"""/start and /help. Only reachable by members -- AccessMiddleware gates the rest."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from powerbank.core.roles import Role
from powerbank.db.models import User

router = Router(name="start")

MEMBER_HELP = """<b>Power Bank</b>

/start — this message
/help — this message"""

STAFF_HELP = """

<b>Admin</b>
/add &lt;id|@user&gt; [user|admin] — grant access
/remove &lt;id|@user&gt; — revoke access
/members — list everyone with access
/who &lt;id|@user&gt; — look someone up
/attempts — who tried to get in"""


@router.message(CommandStart())
async def cmd_start(message: Message, user: User) -> None:
    name = user.first_name or "there"
    await message.answer(
        f"Welcome to {hbold('Power Bank')}, {name}!\n"
        f"You are signed in as {hbold(user.role.label)}.\n\n"
        "Your account is being set up. More coming soon."
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    text = MEMBER_HELP
    if user.role.rank >= Role.ADMIN.rank:
        text += STAFF_HELP
    await message.answer(text)
