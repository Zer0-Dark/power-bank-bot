"""Membership management, by command or by button.

Both entry points converge on the same service calls and the same view text.

Every handler is gated by IsStaff -- on messages *and* callback queries, since
a callback is just as much an entry point as a command. The service layer
re-checks authority independently, so a filter mistake alone cannot escalate
rights.
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.bot import views
from powerbank.bot.callbacks import ConfirmCb, EmployeeCardsCb, Nav, NavCb, RoleCb
from powerbank.bot.commands import sync_for_user
from powerbank.bot.filters import IsStaff
from powerbank.bot.keyboards import menu
from powerbank.bot.screens import send_card_image, show
from powerbank.core.config import Settings
from powerbank.core.exceptions import UserFacingError
from powerbank.core.roles import Role
from powerbank.db.models import User
from powerbank.services import access, cards, users

router = Router(name="admin")
router.message.filter(IsStaff)
router.callback_query.filter(IsStaff)

ROLE_WORDS = {"user": Role.USER, "u": Role.USER, "admin": Role.ADMIN, "a": Role.ADMIN}

# Typed input never begins with a slash -- that is a command escaping the flow.
NotACommand = ~F.text.startswith("/")


class AddMember(StatesGroup):
    target = State()
    role = State()


class RemoveMember(StatesGroup):
    target = State()


class Lookup(StatesGroup):
    target = State()


class EmployeeCards(StatesGroup):
    target = State()


class FindCard(StatesGroup):
    query = State()


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
        raise UserFacingError(views.unknown_username(text))
    return found.telegram_id


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------


@router.callback_query(NavCb.filter(F.to == Nav.ADMIN))
async def open_panel(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show(query, views.admin_panel(), menu.admin_menu())


@router.callback_query(NavCb.filter(F.to == Nav.MEMBERS))
async def open_members(query: CallbackQuery, session: AsyncSession) -> None:
    members = await users.list_by_roles(session, (Role.SUPER_ADMIN, Role.ADMIN, Role.USER))
    await show(query, views.members_list(members), menu.back_to(Nav.ADMIN))


@router.callback_query(NavCb.filter(F.to == Nav.ATTEMPTS))
async def open_attempts(query: CallbackQuery, session: AsyncSession) -> None:
    knocking = await users.list_recent_denied(session)
    await show(query, views.attempts_list(knocking), menu.back_to(Nav.ADMIN))


# --------------------------------------------------------------------------
# Add flow
# --------------------------------------------------------------------------


@router.callback_query(NavCb.filter(F.to == Nav.ADD))
async def add_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddMember.target)
    await show(query, views.ASK_TARGET_ADD, menu.cancel_only())


@router.message(StateFilter(AddMember.target), NotACommand)
async def add_got_target(message: Message, state: FSMContext, session: AsyncSession) -> None:
    telegram_id = await _resolve_target(session, message.text or "")
    await state.update_data(telegram_id=telegram_id)
    await state.set_state(AddMember.role)
    await message.answer(views.ASK_ROLE, reply_markup=menu.role_choice())


@router.callback_query(StateFilter(AddMember.role), RoleCb.filter())
async def add_got_role(
    query: CallbackQuery,
    callback_data: RoleCb,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    data = await state.get_data()
    await state.clear()

    result = await access.grant_role(session, user, data["telegram_id"], callback_data.role)
    # Their "/" menu must reflect the new role without waiting for a restart.
    await sync_for_user(query.bot, result.user.telegram_id, callback_data.role)

    await show(
        query,
        views.granted(result.user, callback_data.role, is_new=result.is_new_member),
        menu.back_to(Nav.ADMIN),
    )


# --------------------------------------------------------------------------
# Remove flow
# --------------------------------------------------------------------------


@router.callback_query(NavCb.filter(F.to == Nav.REMOVE))
async def remove_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RemoveMember.target)
    await show(query, views.ASK_TARGET_REMOVE, menu.cancel_only())


@router.message(StateFilter(RemoveMember.target), NotACommand)
async def remove_got_target(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    telegram_id = await _resolve_target(session, message.text or "")

    found = await users.get_by_telegram_id(session, telegram_id)
    if found is None or not found.role.is_member:
        raise UserFacingError(views.NOT_A_MEMBER)

    await message.answer(
        views.confirm_removal(found),
        reply_markup=menu.confirm_removal(telegram_id),
    )


@router.callback_query(ConfirmCb.filter())
async def remove_confirmed(
    query: CallbackQuery,
    callback_data: ConfirmCb,
    session: AsyncSession,
    user: User,
) -> None:
    if not callback_data.yes:
        await show(query, views.CANCELLED, menu.back_to(Nav.ADMIN))
        return

    target = await access.revoke_access(session, user, callback_data.telegram_id)
    await sync_for_user(query.bot, target.telegram_id, Role.NONE)

    await show(query, views.removed(target), menu.back_to(Nav.ADMIN))


# --------------------------------------------------------------------------
# Lookup flow
# --------------------------------------------------------------------------


@router.callback_query(NavCb.filter(F.to == Nav.WHO))
async def who_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Lookup.target)
    await show(query, views.ASK_TARGET_WHO, menu.cancel_only())


@router.message(StateFilter(Lookup.target), NotACommand)
async def who_got_target(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    found = await users.resolve(session, message.text or "")
    if found is None:
        await message.answer(views.NOT_FOUND, reply_markup=menu.back_to(Nav.ADMIN))
        return
    issued = await cards.count_created_by(session, found)
    await message.answer(views.profile(found, issued), reply_markup=menu.back_to(Nav.ADMIN))


# --------------------------------------------------------------------------
# Card oversight
# --------------------------------------------------------------------------


async def _employee_cards_reply(message: Message, session: AsyncSession, found: User) -> None:
    issued = await cards.list_created_by(session, found)
    total = await cards.count_created_by(session, found)
    await message.answer(
        views.employee_cards(found, issued, total), reply_markup=menu.back_to(Nav.CARDS)
    )


async def _card_lookup_reply(
    message: Message, session: AsyncSession, settings: Settings, query: str
) -> None:
    card = await cards.find_card(session, query)
    if card is None:
        await message.answer(views.CARD_NOT_FOUND, reply_markup=menu.back_to(Nav.ADMIN))
        return
    issuer = await session.get(User, card.created_by_id) if card.created_by_id else None
    await message.answer(views.card_details(card, issuer), reply_markup=menu.back_to(Nav.ADMIN))
    await send_card_image(message, card, settings)


@router.callback_query(NavCb.filter(F.to == Nav.CARDS))
async def open_cards_summary(query: CallbackQuery, session: AsyncSession) -> None:
    rows = await cards.issue_counts(session)
    await show(query, views.issue_summary(rows), menu.issue_summary_kb(rows))


@router.callback_query(EmployeeCardsCb.filter())
async def open_employee_cards(
    query: CallbackQuery, callback_data: EmployeeCardsCb, session: AsyncSession
) -> None:
    found = await users.get_by_telegram_id(session, callback_data.telegram_id)
    if found is None:
        await show(query, views.NOT_FOUND, menu.back_to(Nav.CARDS))
        return
    issued = await cards.list_created_by(session, found)
    total = await cards.count_created_by(session, found)
    await show(query, views.employee_cards(found, issued, total), menu.back_to(Nav.CARDS))


@router.callback_query(NavCb.filter(F.to == Nav.CARD_LOOKUP))
async def card_lookup_start(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FindCard.query)
    await show(query, views.ASK_CARD_QUERY, menu.cancel_only())


@router.message(StateFilter(FindCard.query), NotACommand)
async def card_lookup_got_query(
    message: Message, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    await state.clear()
    await _card_lookup_reply(message, session, settings, message.text or "")


@router.message(StateFilter(EmployeeCards.target), NotACommand)
async def employee_cards_got_target(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    found = await users.resolve(session, message.text or "")
    if found is None or not found.role.is_member:
        await message.answer(views.NOT_A_MEMBER, reply_markup=menu.back_to(Nav.CARDS))
        return
    await _employee_cards_reply(message, session, found)


# --------------------------------------------------------------------------
# Commands (equivalent to the buttons above)
# --------------------------------------------------------------------------


@router.message(Command("add"))
async def cmd_add(
    message: Message, command: CommandObject, session: AsyncSession, user: User, state: FSMContext
) -> None:
    """/add <id|@username> [user|admin]"""
    await state.clear()
    args = (command.args or "").split()

    if not args:  # no arguments -- fall into the guided flow
        await state.set_state(AddMember.target)
        await message.answer(views.ASK_TARGET_ADD, reply_markup=menu.cancel_only())
        return

    role = ROLE_WORDS.get(args[1].lower()) if len(args) > 1 else Role.USER
    if role is None:
        await message.answer(views.BAD_ROLE)
        return

    telegram_id = await _resolve_target(session, args[0])
    result = await access.grant_role(session, user, telegram_id, role)
    await sync_for_user(message.bot, telegram_id, role)

    await message.answer(
        views.granted(result.user, role, is_new=result.is_new_member),
        reply_markup=menu.back_to(Nav.ADMIN),
    )


@router.message(Command("remove"))
async def cmd_remove(
    message: Message, command: CommandObject, session: AsyncSession, state: FSMContext
) -> None:
    """/remove <id|@username>"""
    await state.clear()
    if not command.args:
        await state.set_state(RemoveMember.target)
        await message.answer(views.ASK_TARGET_REMOVE, reply_markup=menu.cancel_only())
        return

    await remove_got_target(message, state, session)


@router.message(Command("members"))
async def cmd_members(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    members = await users.list_by_roles(session, (Role.SUPER_ADMIN, Role.ADMIN, Role.USER))
    await message.answer(views.members_list(members), reply_markup=menu.back_to(Nav.ADMIN))


@router.message(Command("attempts"))
async def cmd_attempts(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    knocking = await users.list_recent_denied(session)
    await message.answer(views.attempts_list(knocking), reply_markup=menu.back_to(Nav.ADMIN))


@router.message(Command("who"))
async def cmd_who(
    message: Message, command: CommandObject, session: AsyncSession, state: FSMContext
) -> None:
    """/who <id|@username>"""
    await state.clear()
    if not command.args:
        await state.set_state(Lookup.target)
        await message.answer(views.ASK_TARGET_WHO, reply_markup=menu.cancel_only())
        return

    found = await users.resolve(session, command.args)
    if found is None:
        await message.answer(views.NOT_FOUND)
        return
    issued = await cards.count_created_by(session, found)
    await message.answer(views.profile(found, issued), reply_markup=menu.back_to(Nav.ADMIN))


@router.message(Command("cards"))
async def cmd_cards(
    message: Message, command: CommandObject, session: AsyncSession, state: FSMContext
) -> None:
    """/cards <id|@employee> -- that employee's issued cards"""
    await state.clear()
    if not command.args:
        await state.set_state(EmployeeCards.target)
        await message.answer(views.ASK_TARGET_CARDS, reply_markup=menu.cancel_only())
        return

    found = await users.resolve(session, command.args)
    if found is None or not found.role.is_member:
        await message.answer(views.NOT_A_MEMBER)
        return
    await _employee_cards_reply(message, session, found)


@router.message(Command("card"))
async def cmd_card(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    state: FSMContext,
    settings: Settings,
) -> None:
    """/card <bank number | name> -- one card, details plus the image"""
    await state.clear()
    if not command.args:
        await state.set_state(FindCard.query)
        await message.answer(views.ASK_CARD_QUERY, reply_markup=menu.cancel_only())
        return

    await _card_lookup_reply(message, session, settings, command.args)
