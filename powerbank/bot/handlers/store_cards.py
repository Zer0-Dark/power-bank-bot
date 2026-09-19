"""Store cards: picking a type, typing a batch size, minting and sending it.

Restricted to super admins, same as coins. A batch is minted once and never
edited. Mirrors `handlers.coins` exactly; the StatesGroup name is unique
across the package on purpose -- see AGENTS.md.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.bot import views
from powerbank.bot.callbacks import Nav, NavCb, StoreCardTypeCb
from powerbank.bot.filters import IsSuperAdmin
from powerbank.bot.keyboards import menu
from powerbank.bot.screens import send_code_card_batch, show
from powerbank.core.config import Settings
from powerbank.core.store_cards import StoreCardType
from powerbank.db.models import User
from powerbank.render.store_cards import render_store_card
from powerbank.services import store_cards
from powerbank.services.batches import clean_batch_count

router = Router(name="store_cards")
router.message.filter(IsSuperAdmin)
router.callback_query.filter(IsSuperAdmin)

# Typed input never begins with a slash -- that is a command escaping the flow.
NotACommand = ~F.text.startswith("/")


class NewStoreCardBatch(StatesGroup):
    card_type = State()
    count = State()


@router.callback_query(NavCb.filter(F.to == Nav.STORE_CARDS))
async def open_panel(query: CallbackQuery, session: AsyncSession) -> None:
    last = await store_cards.last_codes(session)
    await show(query, views.store_cards_panel(last), menu.store_cards_menu())


@router.callback_query(NavCb.filter(F.to == Nav.STORE_CARDS_NEW))
async def start_batch(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewStoreCardBatch.card_type)
    await show(query, views.ASK_STORE_CARD_TYPE, menu.store_card_type_choice())


@router.callback_query(NewStoreCardBatch.card_type, StoreCardTypeCb.filter())
async def got_card_type(
    query: CallbackQuery, callback_data: StoreCardTypeCb, state: FSMContext
) -> None:
    await state.update_data(store_card_type=callback_data.type.value)
    await state.set_state(NewStoreCardBatch.count)
    await show(query, views.ASK_STORE_CARD_COUNT, menu.cancel_only())


@router.message(NewStoreCardBatch.count, NotACommand)
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
    card_type = StoreCardType(data["store_card_type"])

    batch = await store_cards.issue_batch(session, user, card_type, count)

    await message.answer(views.STORE_CARD_RENDERING)
    await send_code_card_batch(
        message,
        batch,
        render_store_card,
        settings.assets_dir,
        caption=views.store_card_batch_caption(card_type, batch),
        keyboard=menu.store_cards_issued_actions(),
    )
