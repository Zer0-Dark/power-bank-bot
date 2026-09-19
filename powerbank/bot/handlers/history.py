"""The audit log: who did what, and when. Super admins only.

Read-only -- the log is written by the service layer as actions happen. The
StatesGroup name is unique across the package on purpose -- see AGENTS.md.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.bot import views
from powerbank.bot.callbacks import HistoryCb, Nav, NavCb
from powerbank.bot.filters import IsSuperAdmin
from powerbank.bot.keyboards import menu
from powerbank.bot.screens import show
from powerbank.core.config import Settings
from powerbank.services import audit, users

router = Router(name="history")
router.message.filter(IsSuperAdmin)
router.callback_query.filter(IsSuperAdmin)

# Typed input never begins with a slash -- that is a command escaping the flow.
NotACommand = ~F.text.startswith("/")


class HistoryPersonFilter(StatesGroup):
    target = State()


async def _page_screen(
    session: AsyncSession, settings: Settings, page: int, who: int
) -> tuple[str, InlineKeyboardMarkup]:
    person = await users.get_by_telegram_id(session, who) if who else None
    result = await audit.history(session, page, person)
    text = views.history_page(result, settings.tz, person)
    return text, menu.history_nav(result.page, result.pages, who if person else 0)


@router.callback_query(NavCb.filter(F.to == Nav.HISTORY))
async def open_history(
    query: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    await state.clear()
    await show(query, *await _page_screen(session, settings, 0, 0))


@router.callback_query(HistoryCb.filter())
async def turn_page(
    query: CallbackQuery, callback_data: HistoryCb, session: AsyncSession, settings: Settings
) -> None:
    await show(query, *await _page_screen(session, settings, callback_data.page, callback_data.who))


@router.callback_query(NavCb.filter(F.to == Nav.HISTORY_PERSON))
async def person_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(HistoryPersonFilter.target)
    await show(query, views.ASK_HISTORY_PERSON, menu.cancel_only())


@router.message(HistoryPersonFilter.target, NotACommand)
async def person_got_target(
    message: Message, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    await state.clear()
    found = await users.resolve(session, message.text or "")
    if found is None:
        await message.answer(views.NOT_FOUND, reply_markup=menu.back_to(Nav.HISTORY))
        return
    text, keyboard = await _page_screen(session, settings, 0, found.telegram_id)
    await message.answer(text, reply_markup=keyboard)
