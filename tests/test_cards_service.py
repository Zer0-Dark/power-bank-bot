"""Card validation and persistence."""

import pytest

from powerbank.core.exceptions import UserFacingError
from powerbank.core.roles import Role
from powerbank.db.models import Card, User
from powerbank.services import cards


async def member(session, tg: int = 1) -> User:
    user = User(telegram_id=tg, role=Role.USER)
    session.add(user)
    await session.flush()
    return user


def details(**overrides) -> cards.CardDetails:
    base = {
        "real_name": "سجاد عدي الفهد",
        "facebook_name": "سجاد عدي الفهد",
        "bank_number": 76,
        "display_username": "MusaGRO",
    }
    return cards.CardDetails(**(base | overrides))


# --- name cleaning ---


def test_collapses_whitespace():
    # Pasted names arrive with newlines and doubled spaces, which would render
    # as gaps on the card.
    assert cards.clean_name("  سجاد   عدي\n الفهد ", "الاسم") == "سجاد عدي الفهد"


def test_rejects_empty_name():
    with pytest.raises(UserFacingError):
        cards.clean_name("   ", "الاسم")


def test_rejects_overlong_name():
    with pytest.raises(UserFacingError):
        cards.clean_name("ا" * 100, "الاسم")


# --- bank number ---


async def test_accepts_plain_digits(session):
    user = await member(session)
    assert await cards.clean_bank_number(session, "76", user) == 76


async def test_leading_zeros_are_the_same_account(session):
    user = await member(session)
    assert await cards.clean_bank_number(session, "00000076", user) == 76


async def test_accepts_arabic_indic_digits(session):
    # An Arabic keyboard produces ٧٦ by default.
    user = await member(session)
    assert await cards.clean_bank_number(session, "٧٦", user) == 76


async def test_rejects_non_numeric(session):
    user = await member(session)
    with pytest.raises(UserFacingError):
        await cards.clean_bank_number(session, "76a", user)


async def test_rejects_zero(session):
    user = await member(session)
    with pytest.raises(UserFacingError):
        await cards.clean_bank_number(session, "0", user)


async def test_rejects_too_many_digits(session):
    user = await member(session)
    with pytest.raises(UserFacingError):
        await cards.clean_bank_number(session, "123456789", user)


async def test_rejects_number_held_by_someone_else(session):
    owner = await member(session, 1)
    await cards.save_card(session, owner, details(bank_number=76))

    other = await member(session, 2)
    with pytest.raises(UserFacingError, match="مستخدم بالفعل"):
        await cards.clean_bank_number(session, "76", other)


async def test_owner_may_keep_their_own_number_when_editing(session):
    owner = await member(session)
    await cards.save_card(session, owner, details(bank_number=76))

    assert await cards.clean_bank_number(session, "76", owner) == 76


# --- persistence ---


async def test_saves_a_new_card(session):
    user = await member(session)

    card = await cards.save_card(session, user, details())

    assert card.bank_number == 76
    assert card.real_name == "سجاد عدي الفهد"
    assert card.display_username == "MusaGRO"


async def test_editing_updates_in_place(session):
    user = await member(session)
    first = await cards.save_card(session, user, details())

    second = await cards.save_card(session, user, details(real_name="اسم جديد"))

    assert first.id == second.id, "a member has exactly one card"
    assert second.real_name == "اسم جديد"


async def test_number_is_zero_padded_for_display(session):
    user = await member(session)
    card = await cards.save_card(session, user, details(bank_number=76))

    assert card.formatted_number == "00000076"


async def test_render_payload_matches_the_layout_fields(session):
    """Guards against a field being renamed in one place but not the other."""
    from powerbank.render.cards import _layout

    user = await member(session)
    card = await cards.save_card(session, user, details())

    assert set(card.as_values()) == set(_layout("assets").fields)


async def test_duplicate_number_is_refused_by_the_database(session):
    """The uniqueness check can lose a race; the constraint is the guarantee."""
    one = await member(session, 1)
    two = await member(session, 2)
    await cards.save_card(session, one, details(bank_number=76))

    session.add(Card(user_id=two.id, bank_number=76, real_name="x",
                     facebook_name="x", display_username="x"))
    with pytest.raises(Exception):  # noqa: B017 - IntegrityError from the driver
        await session.flush()
