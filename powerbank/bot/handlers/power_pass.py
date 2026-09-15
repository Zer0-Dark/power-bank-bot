"""Power-pass cards: picking a design, typing a batch size, minting and sending it.

Restricted to super admins -- these codes are valuable enough that minting them
should not be an ordinary admin action. A batch is minted once and never
edited; each run of the flow inserts `count` new rows tagged with the admin
who ran it, same shape as the account-card issuing flow in `handlers/card.py`.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.bot import views
from powerbank.bot.callbacks import Nav, NavCb, PowerPassTypeCb
from powerbank.bot.filters import IsSuperAdmin
from powerbank.bot.keyboards import menu
from powerbank.bot.screens import send_code_card_batch, show
from powerbank.core.config import Settings
from powerbank.core.power_pass import PowerPassType
from powerbank.db.models import User
from powerbank.render.power_pass import render_power_pass
from powerbank.services import power_pass

router = Router(name="power_pass")
router.message.filter(IsSuperAdmin)
router.callback_query.filter(IsSuperAdmin)

# Typed input never begins with a slash -- that is a command escaping the flow.
NotACommand = ~F.text.startswith("/")


class NewBatch(StatesGroup):
    card_type = State()
    count = State()


@router.callback_query(NavCb.filter(F.to == Nav.POWER_PASS))
async def open_panel(query: CallbackQuery, session: AsyncSession) -> None:
    last = await power_pass.last_codes(session)
    await show(query, views.power_pass_panel(last), menu.power_pass_menu())


@router.callback_query(NavCb.filter(F.to == Nav.POWER_PASS_NEW))
async def start_batch(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewBatch.card_type)
    await show(query, views.ASK_POWER_PASS_TYPE, menu.power_pass_type_choice())


@router.callback_query(NewBatch.card_type, PowerPassTypeCb.filter())
async def got_card_type(
    query: CallbackQuery, callback_data: PowerPassTypeCb, state: FSMContext
) -> None:
    await state.update_data(card_type=callback_data.type.value)
    await state.set_state(NewBatch.count)
    await show(query, views.ASK_POWER_PASS_COUNT, menu.cancel_only())


@router.message(NewBatch.count, NotACommand)
async def got_count(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> None:
    count = power_pass.clean_batch_count(message.text or "")
    data = await state.get_data()
    await state.clear()
    card_type = PowerPassType(data["card_type"])

    batch = await power_pass.issue_batch(session, user, card_type, count)

    await message.answer(views.POWER_PASS_RENDERING)
    await send_code_card_batch(
        message,
        batch,
        render_power_pass,
        settings.assets_dir,
        caption=views.power_pass_batch_caption(card_type, batch),
        keyboard=menu.power_pass_issued_actions(),
    )
