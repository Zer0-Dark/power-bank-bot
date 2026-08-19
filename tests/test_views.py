"""Screen text. Commands and buttons share these, so they are worth pinning."""

from datetime import UTC, datetime

from powerbank.bot import views
from powerbank.core.roles import Role
from powerbank.core.text import FSI, PDI
from powerbank.db.models import User


def make(tg: int, role: Role, username: str | None = None) -> User:
    return User(telegram_id=tg, role=role, username=username, denied_attempts=0)


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
        views.profile(user),
        views.granted(user, Role.ADMIN, is_new=True),
        views.removed(user),
        views.confirm_removal(user),
        views.unknown_username("@ghost"),
    ]
    for text in screens:
        assert text.count(FSI) == text.count(PDI), text


def test_no_isolate_wraps_arabic_text():
    """Isolating a mixed run forces it LTR and reorders the Arabic inside."""
    arabic = set("ابتثجحخدذرزسشصضطظعغفقكلمنهوىيءأإآةً")
    for text in (views.help_text(Role.SUPER_ADMIN), views.MEMBER_HELP):
        for run in isolated_runs(text):
            assert not (arabic & set(run)), f"Arabic inside an isolate: {run!r}"
