"""Router registry.

Order matters: the first matching handler wins. Register specific routers
before broad ones, and keep `errors` last.
"""

from aiogram import Router

from powerbank.bot.handlers import errors, start


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(errors.router)
    return root
