"""Exhaustive permission matrix. Pure functions, no database.

These encode the rules literally as agreed:
  super_admin -> can remove: admin, user
  admin       -> can remove: admin (not self), user
  user        -> can remove: nobody
  nobody      -> can remove a super_admin
"""

import pytest

from powerbank.core.roles import Role, can_grant, can_revoke

ALL = list(Role)


@pytest.mark.parametrize("actor", ALL)
@pytest.mark.parametrize("target", ALL)
def test_grant_matrix(actor: Role, target: Role):
    expected = actor.is_staff and target in {Role.USER, Role.ADMIN}
    assert can_grant(actor, target) is expected


def test_super_admin_cannot_be_granted_by_anyone():
    # Env-seeded only: nobody can mint one, because nobody can remove one.
    assert all(not can_grant(actor, Role.SUPER_ADMIN) for actor in ALL)


def test_nobody_can_grant_the_none_role():
    # Removing access goes through revoke, not grant.
    assert all(not can_grant(actor, Role.NONE) for actor in ALL)


@pytest.mark.parametrize(
    ("actor", "target", "expected"),
    [
        (Role.SUPER_ADMIN, Role.ADMIN, True),
        (Role.SUPER_ADMIN, Role.USER, True),
        (Role.ADMIN, Role.ADMIN, True),
        (Role.ADMIN, Role.USER, True),
        (Role.USER, Role.USER, False),
        (Role.USER, Role.ADMIN, False),
        (Role.NONE, Role.USER, False),
    ],
)
def test_revoke_matrix(actor: Role, target: Role, expected: bool):
    assert can_revoke(actor, target, same_person=False) is expected


@pytest.mark.parametrize("actor", ALL)
def test_super_admin_is_never_revocable(actor: Role):
    assert can_revoke(actor, Role.SUPER_ADMIN, same_person=False) is False


@pytest.mark.parametrize("actor", ALL)
def test_nobody_can_revoke_themselves(actor: Role):
    assert can_revoke(actor, actor, same_person=True) is False


def test_revoking_a_non_member_is_meaningless():
    assert can_revoke(Role.ADMIN, Role.NONE, same_person=False) is False


@pytest.mark.parametrize(
    ("role", "is_member", "is_staff"),
    [
        (Role.NONE, False, False),
        (Role.USER, True, False),
        (Role.ADMIN, True, True),
        (Role.SUPER_ADMIN, True, True),
    ],
)
def test_role_properties(role: Role, is_member: bool, is_staff: bool):
    assert role.is_member is is_member
    assert role.is_staff is is_staff


def test_ranks_are_strictly_ordered():
    ranks = [r.rank for r in (Role.NONE, Role.USER, Role.ADMIN, Role.SUPER_ADMIN)]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)
