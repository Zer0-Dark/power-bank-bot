"""Keyboard shape and callback payload round-tripping.

Callback data is capped at 64 bytes by Telegram and silently breaks buttons if
exceeded, so the packed length is asserted rather than assumed.
"""

import pytest

from powerbank.bot.callbacks import (
    CardTypeCb,
    ConfirmCb,
    EmployeeCardsCb,
    Nav,
    NavCb,
    PowerPassTypeCb,
    RoleCb,
)
from powerbank.bot.keyboards import menu
from powerbank.core.cards import CardType
from powerbank.core.power_pass import PowerPassType
from powerbank.core.roles import Role
from powerbank.db.models import User

TELEGRAM_CALLBACK_LIMIT = 64


def _member(tg: int = 436677576, username: str = "clerk") -> User:
    return User(telegram_id=tg, role=Role.USER, username=username)


def all_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def payloads(markup):
    return [b.callback_data for b in all_buttons(markup)]


# --- role-aware main menu ---


@pytest.mark.parametrize("role", [Role.USER])
def test_plain_user_sees_no_admin_button(role: Role):
    assert NavCb(to=Nav.ADMIN).pack() not in payloads(menu.main_menu(role))


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUPER_ADMIN])
def test_staff_see_the_admin_button(role: Role):
    assert NavCb(to=Nav.ADMIN).pack() in payloads(menu.main_menu(role))


def test_plain_user_main_menu_is_cards_and_help_only():
    found = set(payloads(menu.main_menu(Role.USER)))
    assert found == {NavCb(to=Nav.CARD).pack(), NavCb(to=Nav.HELP).pack()}


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUPER_ADMIN])
def test_staff_see_the_balance_button(role: Role):
    assert NavCb(to=Nav.BALANCE).pack() in payloads(menu.main_menu(role))


def test_admin_menu_covers_every_admin_action():
    found = set(payloads(menu.admin_menu(Role.SUPER_ADMIN)))
    for destination in (
        Nav.MEMBERS,
        Nav.ATTEMPTS,
        Nav.ADD,
        Nav.REMOVE,
        Nav.WHO,
        Nav.CARDS,
        Nav.CARD_LOOKUP,
        Nav.POWER_PASS,
    ):
        assert NavCb(to=destination).pack() in found


def test_plain_admin_sees_no_power_pass_button():
    assert NavCb(to=Nav.POWER_PASS).pack() not in payloads(menu.admin_menu(Role.ADMIN))


def test_super_admin_sees_the_power_pass_button():
    assert NavCb(to=Nav.POWER_PASS).pack() in payloads(menu.admin_menu(Role.SUPER_ADMIN))


def test_every_screen_offers_a_way_back():
    rows = [(_member(), 3)]
    for markup in (
        menu.admin_menu(Role.SUPER_ADMIN),
        menu.back_to(Nav.MAIN),
        menu.cancel_only(),
        menu.card_menu(),
        menu.card_type_choice(),
        menu.card_issued_actions(Role.USER),
        menu.card_issued_actions(Role.ADMIN),
        menu.issue_summary_kb(rows),
        menu.issue_summary_kb([]),
        menu.power_pass_menu(),
        menu.power_pass_type_choice(),
        menu.power_pass_issued_actions(),
    ):
        assert payloads(markup), "a screen with no exit strands the user"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUPER_ADMIN])
def test_staff_can_issue_again_and_view_the_list(role: Role):
    found = set(payloads(menu.card_issued_actions(role)))
    assert NavCb(to=Nav.CARD_NEW).pack() in found
    assert NavCb(to=Nav.CARD).pack() in found


def test_plain_user_can_issue_again_but_gets_no_card_list():
    found = set(payloads(menu.card_issued_actions(Role.USER)))
    assert NavCb(to=Nav.CARD_NEW).pack() in found
    assert NavCb(to=Nav.CARD).pack() not in found


def test_issue_summary_rows_drill_into_an_employee():
    rows = [(_member(1, "a"), 2), (_member(2, "b"), 0)]
    parsed = [
        EmployeeCardsCb.unpack(p)
        for p in payloads(menu.issue_summary_kb(rows))
        if p.startswith("ecards:")
    ]
    assert {p.telegram_id for p in parsed} == {1, 2}
    assert NavCb(to=Nav.ADMIN).pack() in payloads(menu.issue_summary_kb(rows))


# --- payload round-trips ---


def test_nav_payload_round_trips():
    assert NavCb.unpack(NavCb(to=Nav.ADMIN).pack()).to is Nav.ADMIN


def test_role_payload_round_trips():
    assert RoleCb.unpack(RoleCb(role=Role.ADMIN).pack()).role is Role.ADMIN


def test_confirm_payload_carries_its_own_target():
    # The id rides in the payload so a stale button cannot hit a newer target.
    packed = ConfirmCb(yes=True, telegram_id=436677576).pack()
    parsed = ConfirmCb.unpack(packed)

    assert parsed.yes is True
    assert parsed.telegram_id == 436677576


def test_employee_cards_payload_round_trips():
    packed = EmployeeCardsCb(telegram_id=436677576).pack()
    assert EmployeeCardsCb.unpack(packed).telegram_id == 436677576


def test_card_type_choice_offers_every_tier():
    offered = {
        CardTypeCb.unpack(p).type
        for p in payloads(menu.card_type_choice())
        if p.startswith("ctype:")
    }
    assert offered == set(CardType)


def test_card_type_payload_round_trips():
    assert CardTypeCb.unpack(CardTypeCb(type=CardType.ELITE).pack()).type is CardType.ELITE


def test_role_choice_offers_user_and_admin_only():
    offered = {RoleCb.unpack(p).role for p in payloads(menu.role_choice()) if p.startswith("role:")}
    assert offered == {Role.USER, Role.ADMIN}


def test_power_pass_type_choice_offers_every_type():
    offered = {
        PowerPassTypeCb.unpack(p).type
        for p in payloads(menu.power_pass_type_choice())
        if p.startswith("pptype:")
    }
    assert offered == set(PowerPassType)


def test_power_pass_type_payload_round_trips():
    packed = PowerPassTypeCb(type=PowerPassType.SILVER_72).pack()
    assert PowerPassTypeCb.unpack(packed).type is PowerPassType.SILVER_72


# --- Telegram's hard limits ---


@pytest.mark.parametrize(
    "markup",
    [
        menu.main_menu(Role.SUPER_ADMIN),
        menu.admin_menu(Role.SUPER_ADMIN),
        menu.role_choice(),
        menu.cancel_only(),
        menu.confirm_removal(9999999999999),
        menu.card_menu(),
        menu.card_type_choice(),
        menu.card_issued_actions(Role.SUPER_ADMIN),
        menu.issue_summary_kb([(_member(9999999999999, "x" * 20), 999)]),
        menu.power_pass_menu(),
        menu.power_pass_type_choice(),
        menu.power_pass_issued_actions(),
    ],
)
def test_payloads_fit_telegrams_64_byte_limit(markup):
    for payload in payloads(markup):
        assert len(payload.encode()) <= TELEGRAM_CALLBACK_LIMIT, payload


def test_every_button_has_a_label_and_payload():
    for markup in (menu.main_menu(Role.SUPER_ADMIN), menu.admin_menu(Role.SUPER_ADMIN)):
        for button in all_buttons(markup):
            assert button.text.strip()
            assert button.callback_data
