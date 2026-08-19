"""Granting and revoking against real rows, including authority checks."""

import pytest

from powerbank.core.exceptions import PermissionDenied
from powerbank.core.roles import Role
from powerbank.db.models import User
from powerbank.services import access, users


async def make(session, telegram_id: int, role: Role = Role.NONE) -> User:
    user = User(telegram_id=telegram_id, role=role)
    session.add(user)
    await session.flush()
    return user


async def test_admin_adds_a_brand_new_person(session):
    admin = await make(session, 1, Role.ADMIN)

    result = await access.grant_role(session, admin, 999, Role.USER)

    assert result.is_new_member
    assert result.user.role is Role.USER
    assert result.user.granted_by_id == admin.id
    assert result.user.role_granted_at is not None


async def test_granting_creates_row_for_someone_never_seen(session):
    admin = await make(session, 1, Role.ADMIN)
    assert await users.get_by_telegram_id(session, 12345) is None

    await access.grant_role(session, admin, 12345, Role.USER)

    assert await users.get_by_telegram_id(session, 12345) is not None


async def test_admin_can_create_another_admin(session):
    admin = await make(session, 1, Role.ADMIN)
    result = await access.grant_role(session, admin, 2, Role.ADMIN)
    assert result.user.role is Role.ADMIN


async def test_user_cannot_grant_anything(session):
    plain = await make(session, 1, Role.USER)
    with pytest.raises(PermissionDenied):
        await access.grant_role(session, plain, 2, Role.USER)


async def test_nobody_can_grant_super_admin(session):
    boss = await make(session, 1, Role.SUPER_ADMIN)
    with pytest.raises(PermissionDenied):
        await access.grant_role(session, boss, 2, Role.SUPER_ADMIN)


async def test_cannot_change_own_role(session):
    admin = await make(session, 1, Role.ADMIN)
    with pytest.raises(PermissionDenied, match="صلاحيتك بنفسك"):
        await access.grant_role(session, admin, 1, Role.USER)


async def test_admin_cannot_demote_a_super_admin(session):
    admin = await make(session, 1, Role.ADMIN)
    await make(session, 2, Role.SUPER_ADMIN)
    with pytest.raises(PermissionDenied):
        await access.grant_role(session, admin, 2, Role.USER)


async def test_admin_removes_a_user(session):
    admin = await make(session, 1, Role.ADMIN)
    await make(session, 2, Role.USER)

    removed = await access.revoke_access(session, admin, 2)
    assert removed.role is Role.NONE


async def test_admin_removes_another_admin(session):
    admin = await make(session, 1, Role.ADMIN)
    await make(session, 2, Role.ADMIN)

    removed = await access.revoke_access(session, admin, 2)
    assert removed.role is Role.NONE


async def test_admin_cannot_remove_themselves(session):
    admin = await make(session, 1, Role.ADMIN)
    with pytest.raises(PermissionDenied, match="سحب صلاحيتك"):
        await access.revoke_access(session, admin, 1)


async def test_super_admin_cannot_be_removed(session):
    admin = await make(session, 1, Role.ADMIN)
    await make(session, 2, Role.SUPER_ADMIN)
    with pytest.raises(PermissionDenied):
        await access.revoke_access(session, admin, 2)


async def test_user_cannot_remove_anyone(session):
    plain = await make(session, 1, Role.USER)
    await make(session, 2, Role.USER)
    with pytest.raises(PermissionDenied):
        await access.revoke_access(session, plain, 2)


async def test_removing_a_non_member_is_rejected(session):
    admin = await make(session, 1, Role.ADMIN)
    await make(session, 2, Role.NONE)
    with pytest.raises(PermissionDenied, match="ليس عضواً"):
        await access.revoke_access(session, admin, 2)


# --- super admin seeding ---


async def test_seeding_creates_super_admins(session):
    seeded = await access.sync_super_admins(session, [111, 222])

    assert len(seeded) == 2
    found = await users.get_by_telegram_id(session, 111)
    assert found.role is Role.SUPER_ADMIN


async def test_seeding_promotes_an_existing_member(session):
    await make(session, 111, Role.USER)

    await access.sync_super_admins(session, [111])

    found = await users.get_by_telegram_id(session, 111)
    assert found.role is Role.SUPER_ADMIN


async def test_seeding_is_idempotent(session):
    await access.sync_super_admins(session, [111])
    seeded_again = await access.sync_super_admins(session, [111])
    assert seeded_again == []


async def test_seeding_never_demotes_on_removal_from_env(session):
    await access.sync_super_admins(session, [111])

    # 111 dropped from SUPER_ADMIN_IDS -- a config typo must not strip access.
    await access.sync_super_admins(session, [])

    found = await users.get_by_telegram_id(session, 111)
    assert found.role is Role.SUPER_ADMIN
