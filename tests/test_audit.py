"""The audit log: every action writes one line, and the history reads them back."""

import sqlite3
from datetime import UTC

import pytest
from alembic import command
from sqlalchemy import select

from powerbank.bot import views
from powerbank.bot.callbacks import Nav, NavCb
from powerbank.bot.keyboards import menu
from powerbank.core.audit import AuditAction
from powerbank.core.cards import CardType
from powerbank.core.coins import CoinType
from powerbank.core.exceptions import PermissionDenied
from powerbank.core.power_pass import PowerPassType
from powerbank.core.roles import Role
from powerbank.core.store_cards import StoreCardType
from powerbank.db.models import (
    AuditEvent,
    CoinCounter,
    PowerPassCounter,
    StoreCardCounter,
    User,
)
from powerbank.services import access, audit, cards, coins, power_pass, store_cards


async def make(session, telegram_id: int, role: Role = Role.NONE, username=None) -> User:
    user = User(telegram_id=telegram_id, role=role, username=username)
    session.add(user)
    await session.flush()
    return user


async def events(session) -> list[AuditEvent]:
    await session.flush()
    return list(await session.scalars(select(AuditEvent).order_by(AuditEvent.id)))


# --- every action is recorded -------------------------------------------------


async def test_adding_a_member_is_logged_with_actor_target_and_role(session):
    boss = await make(session, 1, Role.SUPER_ADMIN)
    result = await access.grant_role(session, boss, 50, Role.ADMIN)

    (event,) = await events(session)
    assert event.action is AuditAction.MEMBER_ADDED
    assert event.actor_id == boss.id
    assert event.target_id == result.user.id
    assert event.details == {"role": "admin"}


async def test_changing_a_members_role_logs_old_and_new(session):
    boss = await make(session, 1, Role.SUPER_ADMIN)
    await make(session, 50, Role.USER)
    await access.grant_role(session, boss, 50, Role.ADMIN)

    (event,) = await events(session)
    assert event.action is AuditAction.ROLE_CHANGED
    assert event.details == {"role": "admin", "previous_role": "user"}


async def test_removing_a_member_is_logged_with_their_old_role(session):
    boss = await make(session, 1, Role.SUPER_ADMIN)
    gone = await make(session, 50, Role.ADMIN)
    await access.revoke_access(session, boss, 50)

    (event,) = await events(session)
    assert event.action is AuditAction.MEMBER_REMOVED
    assert (event.actor_id, event.target_id) == (boss.id, gone.id)
    assert event.details == {"previous_role": "admin"}


async def test_a_refused_grant_leaves_no_history_line(session):
    plain = await make(session, 1, Role.USER)
    with pytest.raises(PermissionDenied):
        await access.grant_role(session, plain, 50, Role.ADMIN)
    assert await events(session) == []


async def test_seeding_a_super_admin_is_logged_as_the_bot(session):
    await access.sync_super_admins(session, [77])

    (event,) = await events(session)
    assert event.action is AuditAction.SUPER_ADMIN_SEEDED
    assert event.actor_id is None
    assert event.target_id is not None


async def test_issuing_a_card_is_logged_with_its_number_and_name(session):
    emp = await make(session, 1, Role.USER)
    details = cards.CardDetails(
        real_name="Ali",
        facebook_name="Ali F",
        bank_number=76,
        display_username="@ali",
        card_type=CardType.GOLD,
    )
    card = await cards.issue_card(session, emp, details)

    (event,) = await events(session)
    assert event.action is AuditAction.CARD_ISSUED
    assert event.actor_id == emp.id
    assert event.details["bank_number"] == "00000076"
    assert event.details["real_name"] == "Ali"
    assert event.details["card_id"] == card.id


async def test_every_batch_kind_logs_one_line_with_its_code_range(session):
    boss = await make(session, 1, Role.SUPER_ADMIN)
    session.add(CoinCounter(coin_type=CoinType.C500, next_value=151))
    session.add(PowerPassCounter(card_type=PowerPassType.JOIN, next_value=101))
    session.add(StoreCardCounter(card_type=StoreCardType.VISIT_24, next_value=761))
    await session.flush()

    await coins.issue_batch(session, boss, CoinType.C500, 3)
    await power_pass.issue_batch(session, boss, PowerPassType.JOIN, 2)
    await store_cards.issue_batch(session, boss, StoreCardType.VISIT_24, 4)

    logged = await events(session)
    assert [e.action for e in logged] == [
        AuditAction.COIN_BATCH,
        AuditAction.POWER_PASS_BATCH,
        AuditAction.STORE_CARD_BATCH,
    ]
    assert logged[0].details == {
        "type": "500",
        "count": 3,
        "first": "050050000151",
        "last": "050050000153",
    }
    assert logged[2].details["first"] == "0C0P0B0240761"
    assert logged[2].details["last"] == "0C0P0B0240764"


# --- reading it back ----------------------------------------------------------


async def test_history_is_newest_first_and_paged(session):
    boss = await make(session, 1, Role.SUPER_ADMIN)
    for i in range(audit.PAGE_SIZE + 3):
        audit.record(session, AuditAction.ACCESS_DENIED, boss, n=i)
    await session.flush()

    first = await audit.history(session, 0)
    assert first.total == audit.PAGE_SIZE + 3
    assert first.pages == 2
    assert first.events[0].details["n"] == audit.PAGE_SIZE + 2
    assert first.has_older and not first.has_newer

    second = await audit.history(session, 1)
    assert len(second.events) == 3
    assert second.has_newer and not second.has_older


async def test_history_page_is_clamped_to_what_exists(session):
    page = await audit.history(session, 99)
    assert page.page == 0
    assert page.events == []


async def test_person_filter_covers_what_they_did_and_what_was_done_to_them(session):
    boss = await make(session, 1, Role.SUPER_ADMIN)
    other = await make(session, 2, Role.SUPER_ADMIN)
    await access.grant_role(session, boss, 50, Role.ADMIN)  # boss acts on 50
    await access.grant_role(session, other, 60, Role.USER)  # unrelated to 50
    fifty = await session.scalar(select(User).where(User.telegram_id == 50))
    audit.record(session, AuditAction.ACCESS_DENIED, fifty)  # 50 acts
    await session.flush()

    page = await audit.history(session, 0, fifty)
    assert page.total == 2
    assert {e.action for e in page.events} == {
        AuditAction.MEMBER_ADDED,
        AuditAction.ACCESS_DENIED,
    }


# --- display ------------------------------------------------------------------


async def test_every_action_renders_to_text(session):
    boss = await make(session, 1, Role.SUPER_ADMIN, username="boss")
    target = await make(session, 2, Role.USER, username="t<b>")
    samples = {
        AuditAction.MEMBER_ADDED: {"role": "user"},
        AuditAction.ROLE_CHANGED: {"role": "admin", "previous_role": "user"},
        AuditAction.MEMBER_REMOVED: {"previous_role": "admin"},
        AuditAction.SUPER_ADMIN_SEEDED: {},
        AuditAction.CARD_ISSUED: {"card_type": "gold", "bank_number": "00000076", "real_name": "x"},
        AuditAction.CARD_VIEWED: {"query": "<script>", "bank_number": None},
        AuditAction.POWER_PASS_BATCH: {"type": "join", "count": 2, "first": "a", "last": "b"},
        AuditAction.COIN_BATCH: {"type": "500", "count": 2, "first": "a", "last": "b"},
        AuditAction.STORE_CARD_BATCH: {"type": "visit_24", "count": 2, "first": "a", "last": "b"},
        AuditAction.ACCESS_DENIED: {},
    }
    assert set(samples) == set(AuditAction), "add a sample for the new action"
    for action, details in samples.items():
        audit.record(session, action, boss, target=target, **details)
    await session.flush()

    page = await audit.history(session, 0)
    text = views.history_page(page, UTC)
    assert "&lt;script&gt;" in text and "<script>" not in text
    assert "t&lt;b&gt;" in text
    assert "@boss" in text


def test_an_empty_log_says_so():
    assert views.HISTORY_EMPTY in views.history_page(audit.HistoryPage([], 0, 0), UTC)


def test_only_super_admins_see_the_history_button():
    def payloads(kb):
        return [b.callback_data for row in kb.inline_keyboard for b in row]

    button = NavCb(to=Nav.HISTORY).pack()
    assert button in payloads(menu.admin_menu(Role.SUPER_ADMIN))
    assert button not in payloads(menu.admin_menu(Role.ADMIN))


# --- migration backfill -------------------------------------------------------


def test_migration_backfills_members_cards_and_batches(alembic_cfg):
    cfg, db = alembic_cfg
    command.upgrade(cfg, "5b8d3e1f7a2c")

    con = sqlite3.connect(db)
    con.executescript(
        """
        INSERT INTO users (id, telegram_id, is_banned, role, role_granted_at)
            VALUES (1, 10, 0, 'super_admin', '2026-09-01 10:00:00');
        INSERT INTO users (id, telegram_id, is_banned, role, granted_by_id, role_granted_at)
            VALUES (2, 20, 0, 'admin', 1, '2026-09-02 10:00:00');
        INSERT INTO users (id, telegram_id, is_banned, role, granted_by_id, role_granted_at)
            VALUES (3, 30, 0, 'none', 1, '2026-09-03 10:00:00');
        INSERT INTO cards (id, created_by_id, bank_number, real_name, facebook_name,
                           display_username, card_type, created_at)
            VALUES (1, 2, 76, 'Ali', 'f', '@a', 'gold', '2026-09-04 10:00:00');
        INSERT INTO coin_cards (created_by_id, coin_type, code, created_at) VALUES
            (1, '500', '050050000151', '2026-09-05 10:00:00'),
            (1, '500', '050050000152', '2026-09-05 10:00:00'),
            (1, '500', '050050000153', '2026-09-06 10:00:00');
        """
    )
    con.commit()
    con.close()

    command.upgrade(cfg, "head")

    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT action, actor_id, target_id, details FROM audit_log ORDER BY created_at"
        ).fetchall()
    finally:
        con.close()

    assert [r[0] for r in rows] == [
        "super_admin_seeded",
        "member_added",
        "member_removed",
        "card_issued",
        "coin_batch",
        "coin_batch",
    ]
    assert rows[1][1:3] == (1, 2)
    assert '"count": 2' in rows[4][3] and '"backfilled": true' in rows[4][3]
