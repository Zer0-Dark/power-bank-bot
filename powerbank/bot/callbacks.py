"""Typed callback data.

Callback payloads are capped at 64 bytes by Telegram and come from the client,
so they are parsed into these models rather than split by hand -- a malformed
payload fails the filter instead of reaching a handler.
"""

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData

from powerbank.core.roles import Role


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
    CANCEL = "cancel"


class NavCb(CallbackData, prefix="nav"):
    to: Nav


class RoleCb(CallbackData, prefix="role"):
    """Role chosen during the add-member flow."""

    role: Role


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
