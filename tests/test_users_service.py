from powerbank.services.users import TelegramIdentity, get_by_telegram_id, get_or_create

IDENTITY = TelegramIdentity(telegram_id=555, username="abyss", first_name="Abyss")


async def test_creates_user_on_first_contact(session):
    user, created = await get_or_create(session, IDENTITY)

    assert created is True
    assert user.telegram_id == 555
    assert user.username == "abyss"
    assert user.is_banned is False
    assert user.last_seen_at is not None


async def test_second_call_returns_same_user(session):
    first, _ = await get_or_create(session, IDENTITY)
    second, created = await get_or_create(session, IDENTITY)

    assert created is False
    assert first.id == second.id


async def test_profile_fields_refresh_on_return_visit(session):
    await get_or_create(session, IDENTITY)
    renamed = TelegramIdentity(telegram_id=555, username="newname", first_name="New")

    user, created = await get_or_create(session, renamed)

    assert created is False
    assert user.username == "newname"
    assert user.first_name == "New"


async def test_lookup_of_unknown_user_returns_none(session):
    assert await get_by_telegram_id(session, 999) is None
