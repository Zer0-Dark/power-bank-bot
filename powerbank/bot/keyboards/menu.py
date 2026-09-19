"""Inline keyboards. Layout only -- no business logic, no database access."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from powerbank.bot.callbacks import (
    CardTypeCb,
    CoinTypeCb,
    ConfirmCb,
    EmployeeCardsCb,
    Nav,
    NavCb,
    PowerPassTypeCb,
    RoleCb,
    StoreCardTypeCb,
)
from powerbank.core.cards import CardType
from powerbank.core.coins import CoinType
from powerbank.core.power_pass import PowerPassType
from powerbank.core.roles import Role
from powerbank.core.store_cards import StoreCardType


def _nav(text: str, to: Nav) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=NavCb(to=to).pack())


def main_menu(role: Role) -> InlineKeyboardMarkup:
    """The home screen. Plain users only issue cards; staff see extra rows."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🪪 البطاقات", Nav.CARD))
    if role.is_staff:
        builder.row(_nav("💰 الرصيد", Nav.BALANCE))
    builder.row(_nav("❓ المساعدة", Nav.HELP))
    if role.is_staff:
        builder.row(_nav("🛠 لوحة الإدارة", Nav.ADMIN))
    return builder.as_markup()


def admin_menu(role: Role) -> InlineKeyboardMarkup:
    """Batch-minting power-pass codes is valuable enough to gate to super admins."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("👥 الأعضاء", Nav.MEMBERS), _nav("🚪 المحاولات", Nav.ATTEMPTS))
    builder.row(_nav("➕ إضافة", Nav.ADD), _nav("➖ إزالة", Nav.REMOVE))
    builder.row(_nav("🔍 بحث", Nav.WHO))
    builder.row(_nav("🪪 البطاقات", Nav.CARDS), _nav("🔎 بحث بطاقة", Nav.CARD_LOOKUP))
    if role is Role.SUPER_ADMIN:
        builder.row(_nav("🎫 باور باس", Nav.POWER_PASS))
        builder.row(_nav("🪙 عملات", Nav.COINS))
        builder.row(_nav("🛒 بطاقات المتجر", Nav.STORE_CARDS))
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


def card_type_choice() -> InlineKeyboardMarkup:
    """Pick a design before entering the four values. Two tiers per row."""
    builder = InlineKeyboardBuilder()
    buttons = [
        InlineKeyboardButton(
            text=card_type.label, callback_data=CardTypeCb(type=card_type).pack()
        )
        for card_type in CardType
    ]
    for i in range(0, len(buttons), 2):
        builder.row(*buttons[i : i + 2])
    builder.row(_nav("✖️ إلغاء", Nav.CANCEL))
    return builder.as_markup()


def card_issued_actions(role: Role) -> InlineKeyboardMarkup:
    """Attached to a freshly issued card so the employee can keep going.

    Only staff get a way into the issued-cards list; plain users just issue.
    """
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🪪 إصدار بطاقة أخرى", Nav.CARD_NEW))
    if role.is_staff:
        builder.row(_nav("📋 بطاقاتي", Nav.CARD))
    builder.row(_nav("⬅️ رجوع", Nav.MAIN))
    return builder.as_markup()


def power_pass_menu() -> InlineKeyboardMarkup:
    """The landing for "🎫 باور باس": mint a batch, or go back."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🎫 إصدار دفعة", Nav.POWER_PASS_NEW))
    builder.row(_nav("⬅️ رجوع", Nav.ADMIN))
    return builder.as_markup()


def power_pass_type_choice() -> InlineKeyboardMarkup:
    """Pick a design before typing the batch size. One per row -- labels are long."""
    builder = InlineKeyboardBuilder()
    for pp_type in PowerPassType:
        builder.row(
            InlineKeyboardButton(
                text=pp_type.label, callback_data=PowerPassTypeCb(type=pp_type).pack()
            )
        )
    builder.row(_nav("✖️ إلغاء", Nav.CANCEL))
    return builder.as_markup()


def power_pass_issued_actions() -> InlineKeyboardMarkup:
    """Attached after a batch is delivered so the admin can keep going."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🎫 إصدار دفعة أخرى", Nav.POWER_PASS_NEW))
    builder.row(_nav("⬅️ رجوع", Nav.ADMIN))
    return builder.as_markup()


def coins_menu() -> InlineKeyboardMarkup:
    """The landing for "🪙 عملات": mint a batch, or go back."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🪙 إصدار دفعة", Nav.COINS_NEW))
    builder.row(_nav("⬅️ رجوع", Nav.ADMIN))
    return builder.as_markup()


def coin_type_choice() -> InlineKeyboardMarkup:
    """Pick a denomination before typing the batch size. One per row."""
    builder = InlineKeyboardBuilder()
    for coin_type in CoinType:
        builder.row(
            InlineKeyboardButton(
                text=coin_type.label, callback_data=CoinTypeCb(type=coin_type).pack()
            )
        )
    builder.row(_nav("✖️ إلغاء", Nav.CANCEL))
    return builder.as_markup()


def coins_issued_actions() -> InlineKeyboardMarkup:
    """Attached after a batch is delivered so the admin can keep going."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🪙 إصدار دفعة أخرى", Nav.COINS_NEW))
    builder.row(_nav("⬅️ رجوع", Nav.ADMIN))
    return builder.as_markup()


def store_cards_menu() -> InlineKeyboardMarkup:
    """The landing for "🛒 بطاقات المتجر": mint a batch, or go back."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🛒 إصدار دفعة", Nav.STORE_CARDS_NEW))
    builder.row(_nav("⬅️ رجوع", Nav.ADMIN))
    return builder.as_markup()


def store_card_type_choice() -> InlineKeyboardMarkup:
    """Pick a store card type before typing the batch size. One per row."""
    builder = InlineKeyboardBuilder()
    for card_type in StoreCardType:
        builder.row(
            InlineKeyboardButton(
                text=card_type.label, callback_data=StoreCardTypeCb(type=card_type).pack()
            )
        )
    builder.row(_nav("✖️ إلغاء", Nav.CANCEL))
    return builder.as_markup()


def store_cards_issued_actions() -> InlineKeyboardMarkup:
    """Attached after a batch is delivered so the admin can keep going."""
    builder = InlineKeyboardBuilder()
    builder.row(_nav("🛒 إصدار دفعة أخرى", Nav.STORE_CARDS_NEW))
    builder.row(_nav("⬅️ رجوع", Nav.ADMIN))
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
