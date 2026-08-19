"""Reusable handler filters."""

from aiogram.filters import Filter
from aiogram.types import TelegramObject

from powerbank.core.roles import Role
from powerbank.db.models import User


class HasRole(Filter):
    """Passes when the sender's role is at least `minimum`.

    Filters run after the outer middlewares, so `user` is always present for
    any update that reached a handler.
    """

    def __init__(self, minimum: Role) -> None:
        self.minimum = minimum

    async def __call__(self, event: TelegramObject, user: User | None = None) -> bool:
        return user is not None and user.role.rank >= self.minimum.rank


IsStaff = HasRole(Role.ADMIN)
IsSuperAdmin = HasRole(Role.SUPER_ADMIN)
