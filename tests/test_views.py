"""Screen text. Commands and buttons share these, so they are worth pinning."""

from datetime import UTC, datetime

from powerbank.bot import views
from powerbank.core.roles import Role
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
    assert "Abyss" in views.welcome(user)
    assert "Admin" in views.welcome(user)


def test_members_list_groups_by_role():
    members = [make(1, Role.SUPER_ADMIN, "boss"), make(2, Role.USER, "player")]
    text = views.members_list(members)

    assert "Super Admin" in text
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
    assert "4 tries" in text


def test_empty_attempts_list_is_not_blank():
    assert views.attempts_list([]).strip()


def test_profile_flags_a_banned_user():
    user = make(5, Role.USER, "bad")
    user.is_banned = True
    assert "Banned" in views.profile(user)


def test_granted_distinguishes_new_from_updated():
    user = make(6, Role.USER, "fresh")
    assert "Added" in views.granted(user, Role.USER, is_new=True)
    assert "Updated" in views.granted(user, Role.ADMIN, is_new=False)
