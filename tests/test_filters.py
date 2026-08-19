"""Role filters. These guard the button entry points as well as the commands."""

import pytest

from powerbank.bot.filters import HasRole, IsStaff, IsSuperAdmin
from powerbank.core.roles import Role
from powerbank.db.models import User


def as_user(role: Role) -> User:
    return User(telegram_id=1, role=role)


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (Role.NONE, False),
        (Role.USER, False),
        (Role.ADMIN, True),
        (Role.SUPER_ADMIN, True),
    ],
)
async def test_is_staff(role: Role, allowed: bool):
    assert await IsStaff(None, user=as_user(role)) is allowed


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (Role.ADMIN, False),
        (Role.SUPER_ADMIN, True),
    ],
)
async def test_is_super_admin(role: Role, allowed: bool):
    assert await IsSuperAdmin(None, user=as_user(role)) is allowed


async def test_missing_user_is_rejected():
    # Defence in depth: if middleware ever fails to attach a user, deny.
    assert await IsStaff(None, user=None) is False


async def test_filter_is_inclusive_of_its_own_rank():
    assert await HasRole(Role.USER)(None, user=as_user(Role.USER)) is True
