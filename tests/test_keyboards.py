"""Keyboard shape and callback payload round-tripping.

Callback data is capped at 64 bytes by Telegram and silently breaks buttons if
exceeded, so the packed length is asserted rather than assumed.
"""

import pytest

from powerbank.bot.callbacks import ConfirmCb, Nav, NavCb, RoleCb
from powerbank.bot.keyboards import menu
from powerbank.core.roles import Role

TELEGRAM_CALLBACK_LIMIT = 64


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


def test_admin_menu_covers_every_admin_action():
    found = set(payloads(menu.admin_menu()))
    for destination in (Nav.MEMBERS, Nav.ATTEMPTS, Nav.ADD, Nav.REMOVE, Nav.WHO):
        assert NavCb(to=destination).pack() in found


def test_every_screen_offers_a_way_back():
    for markup in (menu.admin_menu(), menu.back_to(Nav.MAIN), menu.cancel_only()):
        assert payloads(markup), "a screen with no exit strands the user"


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


def test_role_choice_offers_user_and_admin_only():
    offered = {RoleCb.unpack(p).role for p in payloads(menu.role_choice()) if p.startswith("role:")}
    assert offered == {Role.USER, Role.ADMIN}


# --- Telegram's hard limits ---


@pytest.mark.parametrize(
    "markup",
    [
        menu.main_menu(Role.SUPER_ADMIN),
        menu.admin_menu(),
        menu.role_choice(),
        menu.cancel_only(),
        menu.confirm_removal(9999999999999),
    ],
)
def test_payloads_fit_telegrams_64_byte_limit(markup):
    for payload in payloads(markup):
        assert len(payload.encode()) <= TELEGRAM_CALLBACK_LIMIT, payload


def test_every_button_has_a_label_and_payload():
    for markup in (menu.main_menu(Role.SUPER_ADMIN), menu.admin_menu()):
        for button in all_buttons(markup):
            assert button.text.strip()
            assert button.callback_data
