"""The account card: entering the four values and rendering the image.

Available to every member. The bank number is issued by the bot, so the flow
only asks for the three typed values.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.bot import views
from powerbank.bot.callbacks import Nav, NavCb
from powerbank.bot.keyboards import menu
from powerbank.bot.screens import show
from powerbank.core.config import Settings
from powerbank.db.models import User
from powerbank.render.cards import render_card
from powerbank.services import cards

router = Router(name="card")

# Typed input never begins with a slash -- that is a command escaping the flow.
NotACommand = ~F.text.startswith("/")


class NewCard(StatesGroup):
    real_name = State()
    facebook_name = State()
    bank_number = State()
    username = State()


async def _send_card(
    event: Message | CallbackQuery,
    card,
    settings: Settings,
    caption: str | None = None,
) -> None:
    """Render and deliver the card image."""
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()

    buffer = await render_card(card, settings.assets_dir)
    await message.answer_photo(
        BufferedInputFile(buffer.getvalue(), filename=f"{card.formatted_number}.png"),
        caption=caption or views.card_caption(card),
        reply_markup=menu.card_actions(),
    )


@router.callback_query(NavCb.filter(F.to == Nav.CARD))
async def open_card(
    query: CallbackQuery, session: AsyncSession, user: User, settings: Settings
) -> None:
    card = await cards.get_for_user(session, user)
    if card is None:
        await show(query, views.CARD_MISSING, menu.card_missing())
        return
    await _send_card(query, card, settings)


@router.callback_query(NavCb.filter(F.to.in_({Nav.CARD_NEW, Nav.CARD_EDIT})))
async def start_form(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewCard.real_name)
    await show(query, views.ASK_REAL_NAME, menu.cancel_only())


@router.message(NewCard.real_name, NotACommand)
async def got_real_name(message: Message, state: FSMContext) -> None:
    value = cards.clean_name(message.text or "", "الاسم الحقيقي")
    await state.update_data(real_name=value)
    await state.set_state(NewCard.facebook_name)
    await message.answer(views.ASK_FACEBOOK_NAME, reply_markup=menu.cancel_only())


@router.message(NewCard.facebook_name, NotACommand)
async def got_facebook_name(message: Message, state: FSMContext) -> None:
    value = cards.clean_name(message.text or "", "الاسم بالفيسبوك")
    await state.update_data(facebook_name=value)
    await state.set_state(NewCard.bank_number)
    await message.answer(views.ASK_BANK_NUMBER, reply_markup=menu.cancel_only())


@router.message(NewCard.bank_number, NotACommand)
async def got_bank_number(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    number = await cards.clean_bank_number(session, message.text or "", user)
    await state.update_data(bank_number=number)
    await state.set_state(NewCard.username)
    await message.answer(views.ASK_CARD_USERNAME, reply_markup=menu.cancel_only())


@router.message(NewCard.username, NotACommand)
async def got_username(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> None:
    value = cards.clean_name(
        message.text or "", "اسم المستخدم", cards.MAX_USERNAME_LENGTH
    )
    data = await state.get_data()
    await state.clear()

    card = await cards.save_card(
        session,
        user,
        cards.CardDetails(
            real_name=data["real_name"],
            facebook_name=data["facebook_name"],
            bank_number=data["bank_number"],
            display_username=value,
        ),
    )

    await message.answer(views.CARD_RENDERING)
    await _send_card(message, card, settings, caption=views.card_caption(card))
