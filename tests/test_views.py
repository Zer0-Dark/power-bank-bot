"""Screen text. Commands and buttons share these, so they are worth pinning."""

from datetime import UTC, datetime

from powerbank.bot import views
from powerbank.core.cards import CardType
from powerbank.core.roles import Role
from powerbank.core.text import FSI, PDI
from powerbank.db.models import Card, User


def make(tg: int, role: Role, username: str | None = None) -> User:
    return User(telegram_id=tg, role=role, username=username, denied_attempts=0)


def card(**overrides) -> Card:
    base = {
        "real_name": "سجاد عدي الفهد",
        "facebook_name": "Sajjad Adi",
        "bank_number": 76,
        "display_username": "MusaGRO",
        "card_type": CardType.DIAMOND,
        "created_at": datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
    }
    return Card(**(base | overrides))


def test_help_hides_admin_commands_from_users():
    text = views.help_text(Role.USER)
    assert "/add" not in text
    assert "/start" in text


def test_help_shows_admin_commands_to_staff():
    text = views.help_text(Role.ADMIN)
    for command in ("/add", "/remove", "/members", "/who", "/attempts"):
        assert command in text


def test_help_lists_every_registered_command():
    """Guards against adding a command and forgetting the help screen."""
    from powerbank.bot.commands import STAFF_COMMANDS

    text = views.help_text(Role.SUPER_ADMIN)
    for command in STAFF_COMMANDS:
        assert f"/{command.command}" in text, f"/{command.command} missing from help"


def test_welcome_names_the_role():
    user = make(1, Role.ADMIN)
    user.first_name = "Abyss"
    text = views.welcome(user)

    assert "Abyss" in text
    assert Role.ADMIN.label in text


def test_members_list_groups_by_role():
    members = [make(1, Role.SUPER_ADMIN, "boss"), make(2, Role.USER, "player")]
    text = views.members_list(members)

    assert Role.SUPER_ADMIN.label in text
    assert "@boss" in text
    assert "@player" in text


def test_empty_members_list_is_not_blank():
    assert views.members_list([]).strip()


def test_attempts_list_shows_counts():
    stranger = make(3, Role.NONE, "knocker")
    stranger.denied_attempts = 4
    stranger.last_denied_at = datetime(2026, 8, 19, 15, 30, tzinfo=UTC)

    text = views.attempts_list([stranger])

    assert "@knocker" in text
    assert "4" in text
    assert "محاولة" in text


def test_empty_attempts_list_is_not_blank():
    assert views.attempts_list([]).strip()


def test_profile_flags_a_banned_user():
    user = make(5, Role.USER, "bad")
    user.is_banned = True
    assert "محظور" in views.profile(user)


def test_granted_distinguishes_new_from_updated():
    user = make(6, Role.USER, "fresh")
    assert "تمت إضافة" in views.granted(user, Role.USER, is_new=True)
    assert "تم تحديث" in views.granted(user, Role.ADMIN, is_new=False)


# --- account cards -----------------------------------------------------------


def test_profile_shows_issued_count_for_a_member():
    text = views.profile(make(7, Role.USER, "emp"), 3)
    assert "بطاقات صادرة" in text
    assert "3" in text


def test_profile_omits_issued_count_for_a_stranger():
    assert "بطاقات صادرة" not in views.profile(make(8, Role.NONE, "x"), 0)


def test_my_issued_lists_cards_and_total():
    text = views.my_issued([card(bank_number=76), card(bank_number=77)], 5)
    assert "00000076" in text
    assert "أحدث" in text  # 5 total, 2 shown


def test_my_issued_empty_is_a_prompt():
    assert views.my_issued([], 0).strip()


def test_employee_cards_names_the_employee():
    text = views.employee_cards(make(9, Role.USER, "emp"), [card()], 1)
    assert "@emp" in text
    assert "00000076" in text


def test_issue_summary_ranks_members():
    rows = [(make(1, Role.USER, "a"), 4), (make(2, Role.USER, "b"), 0)]
    text = views.issue_summary(rows)
    assert text.index("@a") < text.index("@b")


def test_card_details_shows_issuer_and_date():
    text = views.card_details(card(), make(1, Role.USER, "clerk"))
    assert "@clerk" in text
    assert "2026-08-30" in text


def test_card_details_tolerates_a_missing_issuer():
    assert "—" in views.card_details(card(), None)


# --- bidi safety ---------------------------------------------------------
#
# Every Latin/numeric run inside an Arabic paragraph must be isolated, or the
# client reorders the punctuation around it. These assert the isolation is
# actually applied, because the bug is invisible in a terminal and only shows
# up on a real device.


def isolated_runs(text: str) -> list[str]:
    """Extract the contents of every FSI...PDI span."""
    runs, depth, buffer = [], 0, ""
    for char in text:
        if char == FSI:
            depth += 1
            continue
        if char == PDI:
            depth -= 1
            if depth == 0:
                runs.append(buffer)
                buffer = ""
            continue
        if depth:
            buffer += char
    return runs


def test_username_is_isolated_in_member_list():
    text = views.members_list([make(1, Role.USER, "Zer00dark")])
    assert any("@Zer00dark" in run for run in isolated_runs(text))


def test_numeric_id_is_isolated():
    text = views.members_list([make(436677576, Role.USER, "x")])
    assert any("436677576" in run for run in isolated_runs(text))


def test_profile_isolates_id_and_handle():
    user = make(436677576, Role.USER, "Zer00dark")
    user.first_name = "Abyss"
    runs = isolated_runs(views.profile(user))

    assert any("436677576" in r for r in runs)
    assert any("@Zer00dark" in r for r in runs)
    assert any("Abyss" in r for r in runs)


def test_attempts_isolates_timestamp():
    stranger = make(3, Role.NONE, "k")
    stranger.denied_attempts = 2
    stranger.last_denied_at = datetime(2026, 8, 19, 15, 30, tzinfo=UTC)

    assert any("08-19" in r for r in isolated_runs(views.attempts_list([stranger])))


def test_card_screens_isolate_numbers_and_dates():
    clerk = make(1, Role.USER, "clerk")
    for run_present, text in (
        ("00000076", views.my_issued([card()], 1)),
        ("2026-08-30", views.my_issued([card()], 1)),
        ("00000076", views.employee_cards(clerk, [card()], 1)),
        ("MusaGRO", views.card_details(card(), clerk)),
        ("4", views.issue_summary([(clerk, 4)])),
    ):
        assert any(run_present in r for r in isolated_runs(text)), (run_present, text)


def test_isolates_are_balanced_on_every_screen():
    """An unclosed isolate corrupts the direction of everything after it."""
    user = make(436677576, Role.ADMIN, "Zer00dark")
    user.first_name = "Abyss"
    user.denied_attempts = 1
    user.last_denied_at = datetime(2026, 8, 19, 15, 30, tzinfo=UTC)

    screens = [
        views.welcome(user),
        views.help_text(Role.SUPER_ADMIN),
        views.admin_panel(),
        views.members_list([user]),
        views.attempts_list([user]),
        views.profile(user, 3),
        views.granted(user, Role.ADMIN, is_new=True),
        views.removed(user),
        views.confirm_removal(user),
        views.unknown_username("@ghost"),
        views.my_issued([card()], 1),
        views.my_issued([], 0),
        views.employee_cards(user, [card()], 1),
        views.employee_cards(user, [], 0),
        views.issue_summary([(user, 3)]),
        views.issue_summary([]),
        views.card_details(card(), user),
        views.card_details(card(), None),
        views.card_caption(card()),
    ]
    for text in screens:
        assert text.count(FSI) == text.count(PDI), text


def test_no_isolate_wraps_arabic_text():
    """Isolating a mixed run forces it LTR and reorders the Arabic inside."""
    arabic = set("ابتثجحخدذرزسشصضطظعغفقكلمنهوىيءأإآةً")
    for text in (views.help_text(Role.SUPER_ADMIN), views.MEMBER_HELP):
        for run in isolated_runs(text):
            assert not (arabic & set(run)), f"Arabic inside an isolate: {run!r}"
