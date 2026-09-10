"""Card validation, issuing, and lookup."""

import pytest

from powerbank.core.exceptions import UserFacingError
from powerbank.core.roles import Role
from powerbank.db.models import Card, User
from powerbank.services import cards


async def employee(session, tg: int = 1) -> User:
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


async def issue(session, emp: User, **overrides) -> Card:
    return await cards.issue_card(session, emp, details(**overrides))


# --- name cleaning ---


def test_collapses_whitespace():
    assert cards.clean_name("  سجاد   عدي\n الفهد ", "الاسم") == "سجاد عدي الفهد"


def test_rejects_empty_name():
    with pytest.raises(UserFacingError):
        cards.clean_name("   ", "الاسم")


def test_rejects_overlong_name():
    with pytest.raises(UserFacingError):
        cards.clean_name("ا" * 100, "الاسم")


# --- bank number normalisation ---


def test_normalize_accepts_plain_digits():
    assert cards._normalize_bank_number("76") == 76


def test_normalize_leading_zeros_are_the_same_account():
    assert cards._normalize_bank_number("00000076") == 76


def test_normalize_accepts_arabic_indic_digits():
    assert cards._normalize_bank_number("٧٦") == 76


def test_normalize_rejects_non_numeric():
    with pytest.raises(UserFacingError):
        cards._normalize_bank_number("76a")


def test_normalize_rejects_zero():
    with pytest.raises(UserFacingError):
        cards._normalize_bank_number("0")


def test_normalize_rejects_too_many_digits():
    with pytest.raises(UserFacingError):
        cards._normalize_bank_number("123456789")


async def test_clean_bank_number_rejects_any_existing_holder(session):
    emp = await employee(session)
    await issue(session, emp, bank_number=76)

    with pytest.raises(UserFacingError, match="مستخدم بالفعل"):
        await cards.clean_bank_number(session, "76")


async def test_clean_bank_number_accepts_a_free_number(session):
    await employee(session)
    assert await cards.clean_bank_number(session, "٠٠٠٠٧٦") == 76


# --- issuing ---


async def test_issue_card_tags_the_employee(session):
    emp = await employee(session)
    card = await issue(session, emp)

    assert card.created_by_id == emp.id
    assert card.bank_number == 76
    assert card.display_username == "MusaGRO"


async def test_an_employee_issues_many_cards(session):
    emp = await employee(session)
    first = await issue(session, emp, bank_number=1)
    second = await issue(session, emp, bank_number=2)

    assert first.id != second.id
    assert await cards.count_created_by(session, emp) == 2


async def test_number_is_zero_padded_for_display(session):
    emp = await employee(session)
    card = await issue(session, emp, bank_number=76)
    assert card.formatted_number == "00000076"


async def test_duplicate_number_is_refused_by_the_database(session):
    """The uniqueness check can lose a race; the constraint is the guarantee."""
    emp = await employee(session)
    await issue(session, emp, bank_number=76)

    session.add(
        Card(
            created_by_id=emp.id,
            bank_number=76,
            real_name="x",
            facebook_name="x",
            display_username="x",
        )
    )
    with pytest.raises(Exception):  # noqa: B017 - IntegrityError from the driver
        await session.flush()


async def test_render_payload_matches_every_layout(session):
    """Guards against a field being renamed in one place but not the other."""
    from powerbank.core.cards import CardType
    from powerbank.render.cards import _layout

    emp = await employee(session)
    card = await issue(session, emp)

    for card_type in CardType:
        assert set(card.as_values()) == set(_layout("assets", card_type).fields)


async def test_issue_card_records_the_chosen_tier(session):
    from powerbank.core.cards import CardType

    emp = await employee(session)
    card = await issue(session, emp, card_type=CardType.GOLD)
    assert card.card_type is CardType.GOLD


async def test_issue_card_defaults_to_diamond(session):
    from powerbank.core.cards import CardType

    emp = await employee(session)
    card = await issue(session, emp)
    assert card.card_type is CardType.DIAMOND


# --- listing and counting ---


async def test_list_created_by_is_scoped_to_the_employee(session):
    alice = await employee(session, 1)
    bob = await employee(session, 2)
    await issue(session, alice, bank_number=1)
    await issue(session, alice, bank_number=2)
    await issue(session, bob, bank_number=3)

    mine = await cards.list_created_by(session, alice)
    assert {c.bank_number for c in mine} == {1, 2}


async def test_list_created_by_is_newest_first_with_id_tiebreak(session):
    emp = await employee(session)
    a = await issue(session, emp, bank_number=1)
    b = await issue(session, emp, bank_number=2)
    c = await issue(session, emp, bank_number=3)

    ids = [row.id for row in await cards.list_created_by(session, emp)]
    assert ids == [c.id, b.id, a.id]


async def test_list_created_by_respects_the_limit(session):
    emp = await employee(session)
    for n in range(5):
        await issue(session, emp, bank_number=n + 1)

    assert len(await cards.list_created_by(session, emp, limit=3)) == 3


async def test_count_created_by_is_zero_for_a_fresh_employee(session):
    emp = await employee(session)
    assert await cards.count_created_by(session, emp) == 0


async def test_issue_counts_orders_by_volume_and_covers_every_member(session):
    alice = await employee(session, 1)
    bob = await employee(session, 2)
    await employee(session, 3)  # carol, issues nothing
    session.add(User(telegram_id=9, role=Role.NONE))  # stranger, excluded
    await session.flush()

    await issue(session, alice, bank_number=1)
    await issue(session, alice, bank_number=2)
    await issue(session, bob, bank_number=3)

    rows = await cards.issue_counts(session)
    assert [(u.telegram_id, n) for u, n in rows] == [(1, 2), (2, 1), (3, 0)]


# --- find_card ---


async def test_find_card_by_bank_number(session):
    emp = await employee(session)
    await issue(session, emp, bank_number=76)

    for query in ("76", "00000076", "٧٦"):
        found = await cards.find_card(session, query)
        assert found is not None and found.bank_number == 76


async def test_find_card_by_partial_case_insensitive_name(session):
    emp = await employee(session)
    await issue(session, emp, bank_number=76, facebook_name="Sajjad Adi")

    assert (await cards.find_card(session, "sajjad")).bank_number == 76
    assert (await cards.find_card(session, "عدي")).bank_number == 76


async def test_find_card_returns_none_when_nothing_matches(session):
    await employee(session)
    assert await cards.find_card(session, "nobody") is None
    assert await cards.find_card(session, "999") is None
