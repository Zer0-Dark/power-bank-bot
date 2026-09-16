"""Coin notes: picking a denomination, typing a batch size, minting and sending it.

Restricted to super admins -- these codes are valuable enough that minting them
should not be an ordinary admin action. A batch is minted once and never
edited. Mirrors `handlers.power_pass` exactly; the two flows differ only in
domain type and rendering.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.bot import views
from powerbank.bot.callbacks import CoinTypeCb, Nav, NavCb
from powerbank.bot.filters import IsSuperAdmin
from powerbank.bot.keyboards import menu
from powerbank.bot.screens import send_code_card_batch, show
from powerbank.core.coins import CoinType
from powerbank.core.config import Settings
from powerbank.db.models import User
from powerbank.render.coins import render_coin
from powerbank.services import coins
from powerbank.services.batches import clean_batch_count

router = Router(name="coins")
router.message.filter(IsSuperAdmin)
router.callback_query.filter(IsSuperAdmin)

# Typed input never begins with a slash -- that is a command escaping the flow.
NotACommand = ~F.text.startswith("/")


class NewCoinBatch(StatesGroup):
    coin_type = State()
    count = State()


@router.callback_query(NavCb.filter(F.to == Nav.COINS))
async def open_panel(query: CallbackQuery, session: AsyncSession) -> None:
    last = await coins.last_codes(session)
    await show(query, views.coins_panel(last), menu.coins_menu())


@router.callback_query(NavCb.filter(F.to == Nav.COINS_NEW))
async def start_batch(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewCoinBatch.coin_type)
    await show(query, views.ASK_COIN_TYPE, menu.coin_type_choice())


@router.callback_query(NewCoinBatch.coin_type, CoinTypeCb.filter())
async def got_coin_type(
    query: CallbackQuery, callback_data: CoinTypeCb, state: FSMContext
) -> None:
    await state.update_data(coin_type=callback_data.type.value)
    await state.set_state(NewCoinBatch.count)
    await show(query, views.ASK_COIN_COUNT, menu.cancel_only())


@router.message(NewCoinBatch.count, NotACommand)
async def got_count(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> None:
    count = clean_batch_count(message.text or "")
    data = await state.get_data()
    await state.clear()
    coin_type = CoinType(data["coin_type"])

    batch = await coins.issue_batch(session, user, coin_type, count)

    await message.answer(views.COIN_RENDERING)
    await send_code_card_batch(
        message,
        batch,
        render_coin,
        settings.assets_dir,
        caption=views.coin_batch_caption(coin_type, batch),
        keyboard=menu.coins_issued_actions(),
    )
