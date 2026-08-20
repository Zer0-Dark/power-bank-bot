"""Router registry.

Order matters: the first matching handler wins.

`menu` is registered before `admin` deliberately. Admin flows wait on free-text
input, and a state handler would otherwise swallow /start and /help -- leaving
someone stuck mid-flow with no way out. Menu first means commands always escape.
"""

from aiogram import Router

from powerbank.bot.handlers import admin, card, errors, menu


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(menu.router)
    root.include_router(card.router)
    root.include_router(admin.router)
    root.include_router(errors.router)
    return root
