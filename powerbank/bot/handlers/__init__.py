"""Router registry.

Order matters: the first matching handler wins.

`menu` is registered before `admin` deliberately. Admin flows wait on free-text
input, and a state handler would otherwise swallow /start and /help -- leaving
someone stuck mid-flow with no way out. Menu first means commands always escape.
"""

from aiogram import Router

from powerbank.bot.handlers import (
    admin,
    card,
    coins,
    errors,
    history,
    menu,
    power_pass,
    store_cards,
)


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(menu.router)
    root.include_router(card.router)
    root.include_router(admin.router)
    root.include_router(power_pass.router)
    root.include_router(coins.router)
    root.include_router(store_cards.router)
    root.include_router(history.router)
    root.include_router(errors.router)
    return root
