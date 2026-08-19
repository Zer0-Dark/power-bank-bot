"""Main menu navigation, available to every member."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from powerbank.bot import views
from powerbank.bot.callbacks import Nav, NavCb
from powerbank.bot.keyboards import menu
from powerbank.bot.screens import show
from powerbank.db.models import User

router = Router(name="menu")


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()  # /start always escapes a half-finished flow
    await show(message, views.welcome(user), menu.main_menu(user.role))


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    await show(message, views.help_text(user.role), menu.back_to(Nav.MAIN))


@router.callback_query(NavCb.filter(F.to == Nav.MAIN))
async def open_main(query: CallbackQuery, user: User, state: FSMContext) -> None:
    await state.clear()
    await show(query, views.welcome(user), menu.main_menu(user.role))


@router.callback_query(NavCb.filter(F.to == Nav.HELP))
async def open_help(query: CallbackQuery, user: User) -> None:
    await show(query, views.help_text(user.role), menu.back_to(Nav.MAIN))


@router.callback_query(NavCb.filter(F.to == Nav.BALANCE))
async def open_balance(query: CallbackQuery, user: User) -> None:
    # Placeholder until the ledger lands in Phase 2.
    await show(query, views.BALANCE_SOON, menu.back_to(Nav.MAIN))


@router.callback_query(NavCb.filter(F.to == Nav.CANCEL))
async def cancel_flow(query: CallbackQuery, user: User, state: FSMContext) -> None:
    await state.clear()
    await show(query, views.CANCELLED, menu.main_menu(user.role))
