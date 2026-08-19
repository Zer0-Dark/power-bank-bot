"""Roles and the permission rules governing them.

Pure domain logic: no database, no aiogram, no I/O. Every rule here is a
predicate that can be exhaustively tested, which is the point -- access control
is where a subtle bug is most expensive.
"""

from enum import StrEnum


class Role(StrEnum):
    """Access level. Stored as a string so the database stays readable."""

    NONE = "none"
    """Seen by the bot but never granted access. Not a member."""

    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

    @property
    def rank(self) -> int:
        return _RANKS[self]

    @property
    def is_member(self) -> bool:
        """Whether this role may use the bot at all."""
        return self is not Role.NONE

    @property
    def is_staff(self) -> bool:
        return self.rank >= Role.ADMIN.rank

    @property
    def label(self) -> str:
        return _LABELS[self]


_RANKS: dict[Role, int] = {
    Role.NONE: 0,
    Role.USER: 1,
    Role.ADMIN: 2,
    Role.SUPER_ADMIN: 3,
}

_LABELS: dict[Role, str] = {
    Role.NONE: "no access",
    Role.USER: "User",
    Role.ADMIN: "Admin",
    Role.SUPER_ADMIN: "Super Admin",
}

# Roles that can be handed out through the bot, by actor role.
# SUPER_ADMIN is deliberately absent: it is seeded from the environment only.
# Nobody can revoke a super admin, so nobody gets to mint one either -- a
# mistaken promotion would otherwise be permanent.
GRANTABLE: dict[Role, frozenset[Role]] = {
    Role.SUPER_ADMIN: frozenset({Role.USER, Role.ADMIN}),
    Role.ADMIN: frozenset({Role.USER, Role.ADMIN}),
    Role.USER: frozenset(),
    Role.NONE: frozenset(),
}


def can_grant(actor: Role, target_new: Role) -> bool:
    """Whether `actor` may assign `target_new` to somebody."""
    return target_new in GRANTABLE.get(actor, frozenset())


def can_revoke(actor: Role, target: Role, *, same_person: bool) -> bool:
    """Whether `actor` may strip `target`'s access.

    Rules:
      - Nobody can revoke a super admin (they are env-managed).
      - Nobody can revoke themselves -- removing your own access is almost
        always a mistake, and for the last admin it is unrecoverable.
      - Admins may revoke other admins and users.
      - Users may revoke nobody.
    """
    if target is Role.SUPER_ADMIN:
        return False
    if same_person:
        return False
    if not target.is_member:
        return False
    return actor.is_staff
