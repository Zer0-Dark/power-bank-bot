"""Granting and revoking access.

Enforces the rules in `core.roles` against real rows, and raises domain
exceptions the bot layer turns into replies. Nothing here formats Telegram
messages.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.audit import AuditAction
from powerbank.core.exceptions import PermissionDenied
from powerbank.core.roles import Role, can_grant, can_revoke
from powerbank.db.models import User
from powerbank.services import audit
from powerbank.services.users import get_by_telegram_id


@dataclass(frozen=True, slots=True)
class GrantResult:
    user: User
    previous_role: Role

    @property
    def was_promotion(self) -> bool:
        return self.user.role.rank > self.previous_role.rank

    @property
    def is_new_member(self) -> bool:
        return not self.previous_role.is_member


async def grant_role(
    session: AsyncSession,
    actor: User,
    telegram_id: int,
    new_role: Role,
) -> GrantResult:
    """Give `telegram_id` the role `new_role`, on `actor`'s authority.

    Creates the row if the person has never messaged the bot, so admins can
    pre-authorise someone who is about to join.
    """
    if not can_grant(actor.role, new_role):
        raise PermissionDenied(f"{actor.role.label}s cannot grant the {new_role.label} role.")

    target = await get_by_telegram_id(session, telegram_id)
    if target is None:
        target = User(telegram_id=telegram_id)
        session.add(target)
        await session.flush()

    if target.id == actor.id:
        raise PermissionDenied("لا يمكنك تغيير صلاحيتك بنفسك.")

    # Changing an existing member's role is a revoke-and-regrant in disguise:
    # demoting an admin needs the same authority as removing one.
    if target.role.is_member and not can_revoke(actor.role, target.role, same_person=False):
        raise PermissionDenied(f"You cannot change the role of a {target.role.label}.")

    previous = target.role
    target.role = new_role
    target.granted_by_id = actor.id
    target.role_granted_at = datetime.now(UTC)

    # Clear the knocking record: they are in now, so the attempts are history
    # and a stale deny-cooldown must not suppress a later, legitimate notice.
    target.denied_attempts = 0
    target.last_denied_at = None

    if previous.is_member:
        audit.record(
            session,
            AuditAction.ROLE_CHANGED,
            actor,
            target=target,
            role=new_role.value,
            previous_role=previous.value,
        )
    else:
        audit.record(session, AuditAction.MEMBER_ADDED, actor, target=target, role=new_role.value)

    await session.flush()

    return GrantResult(user=target, previous_role=previous)


async def revoke_access(session: AsyncSession, actor: User, telegram_id: int) -> User:
    """Strip a person's access entirely, returning them to Role.NONE."""
    target = await get_by_telegram_id(session, telegram_id)
    if target is None or not target.role.is_member:
        raise PermissionDenied("هذا الشخص ليس عضواً.")

    if not can_revoke(actor.role, target.role, same_person=target.id == actor.id):
        if target.id == actor.id:
            raise PermissionDenied("لا يمكنك سحب صلاحيتك بنفسك.")
        raise PermissionDenied(f"لا يمكنك إزالة {target.role.label}.")

    previous = target.role
    target.role = Role.NONE
    target.granted_by_id = actor.id
    target.role_granted_at = datetime.now(UTC)
    audit.record(
        session, AuditAction.MEMBER_REMOVED, actor, target=target, previous_role=previous.value
    )
    await session.flush()
    return target


async def sync_super_admins(session: AsyncSession, telegram_ids: list[int]) -> list[User]:
    """Make the env-listed ids super admins at startup.

    Only ever promotes. Removing an id from the env does NOT demote them --
    that would silently strip access on a config typo. Demote deliberately with
    an explicit command instead.
    """
    seeded: list[User] = []
    for telegram_id in telegram_ids:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            user = User(telegram_id=telegram_id)
            session.add(user)

        if user.role is not Role.SUPER_ADMIN:
            user.role = Role.SUPER_ADMIN
            user.role_granted_at = datetime.now(UTC)
            seeded.append(user)

    await session.flush()  # new rows need ids before the log can point at them
    for user in seeded:
        audit.record(session, AuditAction.SUPER_ADMIN_SEEDED, None, target=user)
    await session.flush()
    return seeded
