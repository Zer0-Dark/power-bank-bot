"""/start and /help."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold

from powerbank.db.models import User

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, user: User) -> None:
    name = user.first_name or "there"
    await message.answer(
        f"Welcome to {hbold('Power Bank')}, {name}!\n\n"
        "Your account is being set up. More coming soon."
    )
