"""Typed callback data.

Callback payloads are capped at 64 bytes by Telegram and come from the client,
so they are parsed into these models rather than split by hand -- a malformed
payload fails the filter instead of reaching a handler.
"""

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from powerbank.core.cards import CardType
from powerbank.core.coins import CoinType
from powerbank.core.power_pass import PowerPassType
from powerbank.core.roles import Role
from powerbank.core.store_cards import StoreCardType


class Nav(StrEnum):
    """Destinations in the menu tree."""

    MAIN = "main"
    HELP = "help"
    BALANCE = "balance"
    CARD = "card"  # member: my issued-cards list (landing)
    CARD_NEW = "card_new"  # member: start the issuing flow
    ADMIN = "admin"
    MEMBERS = "members"
    ATTEMPTS = "attempts"
    ADD = "add"
    REMOVE = "remove"
    WHO = "who"
    CARDS = "cards"  # admin: all-employees issue summary
    CARD_LOOKUP = "card_find"  # admin: single-card lookup
    POWER_PASS = "power_pass"  # super admin: power-pass panel (per-type totals)
    POWER_PASS_NEW = "power_pass_new"  # super admin: start the batch-issuing flow
    COINS = "coins"  # super admin: coins panel (per-denomination totals)
    COINS_NEW = "coins_new"  # super admin: start the batch-issuing flow
    STORE_CARDS = "store_cards"  # super admin: store-cards panel (per-type last code)
    STORE_CARDS_NEW = "store_cards_new"  # super admin: start the batch-issuing flow
    HISTORY = "history"  # super admin: the audit log, newest first
    HISTORY_PERSON = "history_person"  # super admin: filter the log to one person
    CANCEL = "cancel"


class NavCb(CallbackData, prefix="nav"):
    to: Nav


class RoleCb(CallbackData, prefix="role"):
    """Role chosen during the add-member flow."""

    role: Role


class CardTypeCb(CallbackData, prefix="ctype"):
    """Card design chosen at the start of the issuing flow."""

    type: CardType


class ConfirmCb(CallbackData, prefix="ok"):
    """Confirmation of a destructive action, carrying its own target.

    The id travels in the payload rather than in FSM state so a stale button
    from an older message can never act on a newer target.
    """

    yes: bool
    telegram_id: int


class EmployeeCardsCb(CallbackData, prefix="ecards"):
    """Drill from the issue summary into one employee's issued cards."""

    telegram_id: int


class PowerPassTypeCb(CallbackData, prefix="pptype"):
    """Power-pass design chosen at the start of the batch-issuing flow."""

    type: PowerPassType


class CoinTypeCb(CallbackData, prefix="cointype"):
    """Coin denomination chosen at the start of the batch-issuing flow."""

    type: CoinType


class HistoryCb(CallbackData, prefix="hist"):
    """A page of the audit log. `who` is a Telegram id to filter by, 0 for everyone."""

    page: int
    who: int = 0


class StoreCardTypeCb(CallbackData, prefix="sctype"):
    """Store card type chosen at the start of the batch-issuing flow."""

    type: StoreCardType
