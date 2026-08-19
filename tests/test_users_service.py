"""Contact logging and lookup."""

from powerbank.core.roles import Role
from powerbank.db.models import User
from powerbank.services.users import (
    TelegramIdentity,
    get_by_username,
    list_by_roles,
    list_recent_denied,
    record_contact,
    record_denied_attempt,
    resolve,
)

IDENTITY = TelegramIdentity(telegram_id=555, username="Zer00dark", first_name="Abyss")


async def test_first_contact_creates_a_row_without_access(session):
    user = await record_contact(session, IDENTITY)

    assert user.telegram_id == 555
    assert user.role is Role.NONE, "being seen must never grant access"
    assert user.has_access is False
    assert user.last_seen_at is not None


async def test_second_contact_reuses_the_row(session):
    first = await record_contact(session, IDENTITY)
    second = await record_contact(session, IDENTITY)

    assert first.id == second.id


async def test_contact_does_not_reset_an_existing_role(session):
    user = await record_contact(session, IDENTITY)
    user.role = Role.ADMIN
    await session.flush()

    again = await record_contact(session, IDENTITY)

    assert again.role is Role.ADMIN


async def test_profile_refreshes_so_admin_search_keeps_working(session):
    await record_contact(session, IDENTITY)
    renamed = TelegramIdentity(telegram_id=555, username="newhandle", first_name="New")

    user = await record_contact(session, renamed)

    assert user.username == "newhandle"
    assert await get_by_username(session, "newhandle") is not None


async def test_username_lookup_is_case_insensitive_and_ignores_at(session):
    await record_contact(session, IDENTITY)

    assert await get_by_username(session, "@zer00dark") is not None
    assert await get_by_username(session, "ZER00DARK") is not None


async def test_resolve_accepts_id_or_username(session):
    await record_contact(session, IDENTITY)

    assert (await resolve(session, "555")).telegram_id == 555
    assert (await resolve(session, "@Zer00dark")).telegram_id == 555
    assert await resolve(session, "@nobody") is None


async def test_denied_attempts_accumulate(session):
    user = await record_contact(session, IDENTITY)

    await record_denied_attempt(session, user)
    await record_denied_attempt(session, user)

    assert user.denied_attempts == 2
    assert user.last_denied_at is not None


async def test_recent_denied_lists_only_non_members(session):
    stranger = await record_contact(session, IDENTITY)
    await record_denied_attempt(session, stranger)

    member = await record_contact(session, TelegramIdentity(telegram_id=777, username="member"))
    await record_denied_attempt(session, member)
    member.role = Role.USER
    await session.flush()

    knocking = await list_recent_denied(session)

    assert [u.telegram_id for u in knocking] == [555]


async def test_list_by_roles_orders_by_seniority(session):
    for tg, role in [(1, Role.USER), (2, Role.SUPER_ADMIN), (3, Role.ADMIN)]:
        session.add(User(telegram_id=tg, role=role))
    await session.flush()

    members = await list_by_roles(session, (Role.SUPER_ADMIN, Role.ADMIN, Role.USER))

    assert [m.role for m in members] == [Role.SUPER_ADMIN, Role.ADMIN, Role.USER]


async def test_display_prefers_username(session):
    user = await record_contact(session, IDENTITY)
    assert user.display == "@Zer00dark"

    user.username = None
    assert user.display == "Abyss"

    user.first_name = None
    assert user.display == "555"
