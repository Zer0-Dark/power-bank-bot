"""Inline keyboards. Layout only -- no business logic, no database access."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from powerbank.bot.callbacks import ConfirmCb, EmployeeCardsCb, Nav, NavCb, RoleCb
from powerbank.core.roles import Role


def _nav(text: str, to: Nav) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=NavCb(to=to).pack())


def main_menu(role: Role) -> InlineKeyboardMarkup:
    """The home screen. Staff see an extra row; users never see it exists."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🪪 البطاقات", Nav.CARD))
    builder.row(_nav("💰 الرصيد", Nav.BALANCE))
    builder.row(_nav("❓ المساعدة", Nav.HELP))
    if role.is_staff:
        builder.row(_nav("🛠 لوحة الإدارة", Nav.ADMIN))
    return builder.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_nav("👥 الأعضاء", Nav.MEMBERS), _nav("🚪 المحاولات", Nav.ATTEMPTS))
    builder.row(_nav("➕ إضافة", Nav.ADD), _nav("➖ إزالة", Nav.REMOVE))
    builder.row(_nav("🔍 بحث", Nav.WHO))
    builder.row(_nav("🪪 البطاقات", Nav.CARDS), _nav("🔎 بحث بطاقة", Nav.CARD_LOOKUP))
    builder.row(_nav("⬅️ رجوع", Nav.MAIN))
    return builder.as_markup()


def back_to(to: Nav, text: str = "⬅️ رجوع") -> InlineKeyboardMarkup:
    return InlineKeyboardBuilder().row(_nav(text, to)).as_markup()


def cancel_only() -> InlineKeyboardMarkup:
    """Shown while waiting for typed input, so the user is never stuck."""
    return InlineKeyboardBuilder().row(_nav("✖️ إلغاء", Nav.CANCEL)).as_markup()


def role_choice() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 عضو", callback_data=RoleCb(role=Role.USER).pack()),
        InlineKeyboardButton(text="🛠 مشرف", callback_data=RoleCb(role=Role.ADMIN).pack()),
    )
    builder.row(_nav("✖️ إلغاء", Nav.CANCEL))
    return builder.as_markup()


def confirm_removal(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ نعم، أزله",
            callback_data=ConfirmCb(yes=True, telegram_id=telegram_id).pack(),
        ),
        InlineKeyboardButton(
            text="✖️ إلغاء",
            callback_data=ConfirmCb(yes=False, telegram_id=telegram_id).pack(),
        ),
    )
    return builder.as_markup()


def card_menu() -> InlineKeyboardMarkup:
    """The landing for "🪪 البطاقات": issue a card, or go back."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🪪 إصدار بطاقة", Nav.CARD_NEW))
    builder.row(_nav("⬅️ رجوع", Nav.MAIN))
    return builder.as_markup()


def card_issued_actions() -> InlineKeyboardMarkup:
    """Attached to a freshly issued card so the employee can keep going."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🪪 إصدار بطاقة أخرى", Nav.CARD_NEW))
    builder.row(_nav("📋 بطاقاتي", Nav.CARD))
    builder.row(_nav("⬅️ رجوع", Nav.MAIN))
    return builder.as_markup()


def issue_summary_kb(rows: list[tuple]) -> InlineKeyboardMarkup:
    """One tappable row per member, drilling into their issued cards."""
    builder = InlineKeyboardBuilder()
    for user, count in rows:
        builder.row(
            InlineKeyboardButton(
                text=f"{user.display} ({count})",
                callback_data=EmployeeCardsCb(telegram_id=user.telegram_id).pack(),
            )
        )
    builder.row(_nav("⬅️ رجوع", Nav.ADMIN))
    return builder.as_markup()
