"""Writing and reading the audit log.

`record` is called by the other services, inside the action's own transaction.
It only adds the row -- the action's own flush (or the session commit) writes
it, so a failed action leaves no history line behind.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from powerbank.core.audit import AuditAction
from powerbank.db.models import AuditEvent, User

PAGE_SIZE = 10


def record(
    session: AsyncSession,
    action: AuditAction,
    actor: User | None,
    *,
    target: User | None = None,
    **details: Any,
) -> AuditEvent:
    """Add one history line for `action`, done by `actor` (None = the bot)."""
    event = AuditEvent(
        action=action,
        actor_id=actor.id if actor else None,
        target_id=target.id if target else None,
        details=details,
    )
    session.add(event)
    return event


def record_batch(
    session: AsyncSession, action: AuditAction, actor: User, card_type: str, batch: list
) -> AuditEvent:
    """One line for a whole minted batch: its type, size and code range."""
    return record(
        session,
        action,
        actor,
        type=card_type,
        count=len(batch),
        first=batch[0].code,
        last=batch[-1].code,
    )


@dataclass(frozen=True, slots=True)
class HistoryPage:
    events: list[AuditEvent]
    page: int
    total: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // PAGE_SIZE))

    @property
    def has_newer(self) -> bool:
        return self.page > 0

    @property
    def has_older(self) -> bool:
        return self.page + 1 < self.pages


async def history(session: AsyncSession, page: int = 0, person: User | None = None) -> HistoryPage:
    """Newest-first page of the log, optionally only lines involving `person`.

    "Involving" means they did it *or* it was done to them, so a member's
    page shows both the cards they issued and who added or removed them.
    """
    where = []
    if person is not None:
        where.append(or_(AuditEvent.actor_id == person.id, AuditEvent.target_id == person.id))

    total = await session.scalar(select(func.count()).select_from(AuditEvent).where(*where))
    pages = max(1, -(-(total or 0) // PAGE_SIZE))
    page = min(max(page, 0), pages - 1)

    result = await session.scalars(
        select(AuditEvent)
        .where(*where)
        .options(selectinload(AuditEvent.actor), selectinload(AuditEvent.target))
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(page * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    return HistoryPage(events=list(result), page=page, total=total or 0)
