"""Inline keyboards. Layout only -- no business logic, no database access."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from powerbank.bot.callbacks import ConfirmCb, Nav, NavCb, RoleCb
from powerbank.core.roles import Role


def _nav(text: str, to: Nav) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=NavCb(to=to).pack())


def main_menu(role: Role) -> InlineKeyboardMarkup:
    """The home screen. Staff see an extra row; users never see it exists."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("💰 Balance", Nav.BALANCE))
    builder.row(_nav("❓ Help", Nav.HELP))
    if role.is_staff:
        builder.row(_nav("🛠 Admin panel", Nav.ADMIN))
    return builder.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_nav("👥 Members", Nav.MEMBERS), _nav("🚪 Attempts", Nav.ATTEMPTS))
    builder.row(_nav("➕ Add", Nav.ADD), _nav("➖ Remove", Nav.REMOVE))
    builder.row(_nav("🔍 Look up", Nav.WHO))
    builder.row(_nav("⬅️ Back", Nav.MAIN))
    return builder.as_markup()


def back_to(to: Nav, text: str = "⬅️ Back") -> InlineKeyboardMarkup:
    return InlineKeyboardBuilder().row(_nav(text, to)).as_markup()


def cancel_only() -> InlineKeyboardMarkup:
    """Shown while waiting for typed input, so the user is never stuck."""
    return InlineKeyboardBuilder().row(_nav("✖️ Cancel", Nav.CANCEL)).as_markup()


def role_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 User", callback_data=RoleCb(role=Role.USER).pack()),
        InlineKeyboardButton(text="🛠 Admin", callback_data=RoleCb(role=Role.ADMIN).pack()),
    )
    builder.row(_nav("✖️ Cancel", Nav.CANCEL))
    return builder.as_markup()


def confirm_removal(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Yes, remove",
            callback_data=ConfirmCb(yes=True, telegram_id=telegram_id).pack(),
        ),
        InlineKeyboardButton(
            text="✖️ Cancel",
            callback_data=ConfirmCb(yes=False, telegram_id=telegram_id).pack(),
        ),
    )
    return builder.as_markup()
