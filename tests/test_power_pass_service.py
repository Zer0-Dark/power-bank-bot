"""Power-pass code formatting, batch validation, reservation, and issuing."""

import asyncio

import pytest

from powerbank.core.exceptions import UserFacingError
from powerbank.core.power_pass import PowerPassType, format_code
from powerbank.core.roles import Role
from powerbank.db.models import PowerPassCounter, User
from powerbank.services import power_pass


async def admin(session, tg: int = 1) -> User:
    user = User(telegram_id=tg, role=Role.SUPER_ADMIN)
    session.add(user)
    await session.flush()
    return user


async def seed_counter(session, card_type: PowerPassType, next_value: int) -> None:
    session.add(PowerPassCounter(card_type=card_type, next_value=next_value))
    await session.flush()


# --- format_code -----------------------------------------------------------


def test_format_code_matches_the_last_join_code_issued_by_hand():
    assert format_code(PowerPassType.JOIN, 100) == "00CPB0P0PASS000100"


def test_format_code_matches_the_last_gold_72_code_issued_by_hand():
    assert format_code(PowerPassType.GOLD_72, 100) == "0CPB0P0PASS72G0100"


def test_format_code_matches_the_last_silver_72_code_issued_by_hand():
    assert format_code(PowerPassType.SILVER_72, 1) == "0CPB0P0PASS72S0001"


@pytest.mark.parametrize(
    ("card_type", "expected"),
    [
        (PowerPassType.GOLD_48, "0CPB0P0PASS48G0001"),
        (PowerPassType.SILVER_48, "0CPB0P0PASS48S0001"),
        (PowerPassType.GOLD_24, "0CPB0P0PASS24G0001"),
        (PowerPassType.SILVER_24, "0CPB0P0PASS24S0001"),
    ],
)
def test_format_code_matches_every_starting_point_given_by_hand(card_type, expected):
    assert format_code(card_type, 1) == expected


def test_every_code_is_eighteen_characters_regardless_of_type():
    for card_type in PowerPassType:
        assert len(format_code(card_type, 1)) == 18
        assert len(format_code(card_type, 9999)) == 18


def test_format_code_is_injective_across_consecutive_numbers():
    codes = {format_code(PowerPassType.GOLD_72, n) for n in range(1, 50)}
    assert len(codes) == 49


# --- clean_batch_count -------------------------------------------------------


@pytest.mark.parametrize("raw", ["1", "50", "100"])
def test_clean_batch_count_accepts_the_valid_range(raw):
    assert power_pass.clean_batch_count(raw) == int(raw)


@pytest.mark.parametrize("raw", ["0", "101", "-1", "", "abc", "12.5"])
def test_clean_batch_count_rejects_out_of_range_or_non_numeric(raw):
    with pytest.raises(UserFacingError):
        power_pass.clean_batch_count(raw)


def test_clean_batch_count_collapses_surrounding_whitespace():
    assert power_pass.clean_batch_count("  42  ") == 42


# --- reserve_codes -----------------------------------------------------------


async def test_reserve_codes_starts_at_the_seeded_value(session):
    await seed_counter(session, PowerPassType.GOLD_24, 1)
    reserved = await power_pass.reserve_codes(session, PowerPassType.GOLD_24, 5)
    assert list(reserved) == [1, 2, 3, 4, 5]


async def test_reserve_codes_continues_from_where_it_left_off(session):
    await seed_counter(session, PowerPassType.GOLD_24, 1)
    await power_pass.reserve_codes(session, PowerPassType.GOLD_24, 5)
    second = await power_pass.reserve_codes(session, PowerPassType.GOLD_24, 3)
    assert list(second) == [6, 7, 8]


async def test_reserve_codes_is_independent_per_type(session):
    await seed_counter(session, PowerPassType.GOLD_24, 1)
    await seed_counter(session, PowerPassType.SILVER_24, 1)

    await power_pass.reserve_codes(session, PowerPassType.GOLD_24, 10)
    silver = await power_pass.reserve_codes(session, PowerPassType.SILVER_24, 3)

    assert list(silver) == [1, 2, 3]


async def test_reserve_codes_never_hands_out_the_same_number_twice(session):
    """Concurrent reservations must not overlap.

    Sequential calls are the deterministic proxy for the guarantee that
    matters: a single UPDATE ... RETURNING per call, so two admins minting at
    once cannot both walk away with the same range.
    """
    await seed_counter(session, PowerPassType.SILVER_48, 1)

    seen: set[int] = set()
    for _ in range(10):
        reserved = await power_pass.reserve_codes(session, PowerPassType.SILVER_48, 7)
        assert seen.isdisjoint(reserved), "overlapping range handed out twice"
        seen.update(reserved)


async def test_concurrent_reservations_do_not_overlap(session):
    """The same guarantee, exercised via actual concurrent tasks on one connection."""
    await seed_counter(session, PowerPassType.GOLD_48, 1)

    results = await asyncio.gather(
        *(power_pass.reserve_codes(session, PowerPassType.GOLD_48, 5) for _ in range(4))
    )

    all_numbers = [n for r in results for n in r]
    assert len(all_numbers) == len(set(all_numbers)), "two batches received overlapping numbers"


# --- issue_batch --------------------------------------------------------------


async def test_issue_batch_mints_the_requested_count(session):
    await seed_counter(session, PowerPassType.JOIN, 1)
    emp = await admin(session)

    batch = await power_pass.issue_batch(session, emp, PowerPassType.JOIN, 5)

    assert len(batch) == 5
    assert [c.code for c in batch] == [format_code(PowerPassType.JOIN, n) for n in range(1, 6)]


async def test_issue_batch_tags_every_card_with_the_admin(session):
    await seed_counter(session, PowerPassType.JOIN, 1)
    emp = await admin(session)

    batch = await power_pass.issue_batch(session, emp, PowerPassType.JOIN, 3)
    assert all(card.created_by_id == emp.id for card in batch)


async def test_issue_batch_sets_the_card_type(session):
    await seed_counter(session, PowerPassType.SILVER_72, 1)
    emp = await admin(session)

    batch = await power_pass.issue_batch(session, emp, PowerPassType.SILVER_72, 2)
    assert all(card.card_type is PowerPassType.SILVER_72 for card in batch)


async def test_two_batches_of_the_same_type_never_collide(session):
    await seed_counter(session, PowerPassType.GOLD_72, 1)
    emp = await admin(session)

    first = await power_pass.issue_batch(session, emp, PowerPassType.GOLD_72, 10)
    second = await power_pass.issue_batch(session, emp, PowerPassType.GOLD_72, 10)

    assert {c.code for c in first}.isdisjoint({c.code for c in second})


async def test_last_codes_reflects_the_most_recent_batch_of_each_type(session):
    await seed_counter(session, PowerPassType.JOIN, 1)
    await seed_counter(session, PowerPassType.GOLD_24, 1)
    emp = await admin(session)

    await power_pass.issue_batch(session, emp, PowerPassType.JOIN, 4)
    await power_pass.issue_batch(session, emp, PowerPassType.GOLD_24, 2)

    last = await power_pass.last_codes(session)
    assert last[PowerPassType.JOIN] == format_code(PowerPassType.JOIN, 4)
    assert last[PowerPassType.GOLD_24] == format_code(PowerPassType.GOLD_24, 2)
    assert last[PowerPassType.SILVER_24] is None


async def test_last_codes_covers_every_type_even_with_no_cards_minted(session):
    for card_type in PowerPassType:
        await seed_counter(session, card_type, 1)

    last = await power_pass.last_codes(session)
    assert set(last) == set(PowerPassType)
    assert all(code is None for code in last.values())
