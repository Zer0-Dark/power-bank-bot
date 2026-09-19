"""Store cards: code formatting, issuing, and rendering."""

from pathlib import Path

import pytest
from PIL import Image

from powerbank.core.roles import Role
from powerbank.core.store_cards import StoreCardType, format_code
from powerbank.db.models import StoreCard, StoreCardCounter, User
from powerbank.render.engine import render
from powerbank.render.store_cards import _layout, render_store_card_sync
from powerbank.services import store_cards

ASSETS = Path("assets")
LAYOUTS = {ct: _layout(str(ASSETS), ct) for ct in StoreCardType}


async def admin(session, tg: int = 1) -> User:
    user = User(telegram_id=tg, role=Role.SUPER_ADMIN)
    session.add(user)
    await session.flush()
    return user


async def seed_counter(session, card_type: StoreCardType, next_value: int) -> None:
    session.add(StoreCardCounter(card_type=card_type, next_value=next_value))
    await session.flush()


# --- format_code -----------------------------------------------------------


@pytest.mark.parametrize(
    ("card_type", "n", "expected"),
    [
        (StoreCardType.VISIT_24, 760, "0C0P0B0240760"),
        (StoreCardType.VISIT_48, 300, "0C0P0B0480300"),
        (StoreCardType.VISIT_72, 1279, "0C0P0B0721279"),
        (StoreCardType.TRANSFER_GOLD, 150, "00C0P0B011011100150"),
        (StoreCardType.TRANSFER_SILVER, 600, "00C0P0B02202200600"),
        (StoreCardType.JOIN_RANKED, 204, "00CENTRAL0P0B00204"),
        (StoreCardType.JOIN_UNRANKED, 2000, "00CENTRAL0P0B02000"),
    ],
)
def test_format_code_matches_the_last_codes_issued_by_hand(card_type, n, expected):
    assert format_code(card_type, n) == expected


def test_every_code_fits_the_column():
    for card_type in StoreCardType:
        assert len(format_code(card_type, 99999)) <= 24


# --- issue_batch --------------------------------------------------------------


async def test_issue_batch_continues_from_the_seeded_counter(session):
    await seed_counter(session, StoreCardType.VISIT_24, 761)
    emp = await admin(session)

    batch = await store_cards.issue_batch(session, emp, StoreCardType.VISIT_24, 3)

    assert [c.code for c in batch] == ["0C0P0B0240761", "0C0P0B0240762", "0C0P0B0240763"]
    assert all(c.created_by_id == emp.id for c in batch)
    assert all(c.card_type is StoreCardType.VISIT_24 for c in batch)


async def test_two_batches_of_the_same_type_never_collide(session):
    await seed_counter(session, StoreCardType.TRANSFER_GOLD, 151)
    emp = await admin(session)

    first = await store_cards.issue_batch(session, emp, StoreCardType.TRANSFER_GOLD, 10)
    second = await store_cards.issue_batch(session, emp, StoreCardType.TRANSFER_GOLD, 10)

    assert {c.code for c in first}.isdisjoint({c.code for c in second})


async def test_last_codes_reflects_the_seed_and_later_batches(session):
    await seed_counter(session, StoreCardType.JOIN_RANKED, 205)
    await seed_counter(session, StoreCardType.VISIT_72, 1)
    emp = await admin(session)

    await store_cards.issue_batch(session, emp, StoreCardType.VISIT_72, 2)

    last = await store_cards.last_codes(session)
    assert set(last) == set(StoreCardType)
    assert last[StoreCardType.JOIN_RANKED] == "00CENTRAL0P0B00204"
    assert last[StoreCardType.VISIT_72] == format_code(StoreCardType.VISIT_72, 2)
    assert last[StoreCardType.VISIT_24] is None


# --- rendering ---------------------------------------------------------------


def test_every_type_has_an_existing_template_and_a_code_field():
    for card_type in StoreCardType:
        layout = LAYOUTS[card_type]
        assert set(layout.fields) == {"code"}
        assert layout.template.exists(), f"{card_type.value} template missing"


def test_every_type_code_box_sits_inside_its_template():
    # Left-anchored ("lm"): the box runs from x to x + max_width.
    for card_type in StoreCardType:
        layout = LAYOUTS[card_type]
        width, height = Image.open(layout.template).size
        field = layout.fields["code"]
        assert field.anchor == "lm"
        assert field.x > 0 and field.x + field.max_width <= width, card_type.value
        assert 0 < field.y < height, card_type.value


def test_every_type_renders_a_png_with_the_code_drawn():
    for card_type in StoreCardType:
        layout = LAYOUTS[card_type]
        card = StoreCard(card_type=card_type, code=format_code(card_type, 1))
        filled = Image.open(render_store_card_sync(card, ASSETS))
        assert filled.format == "PNG"
        assert filled.width == layout.output_width
        blank = Image.open(render(layout, {}))
        assert blank.tobytes() != filled.tobytes(), f"nothing drawn on {card_type.value}"
