"""Power-pass cards: reserving codes and minting a batch.

Pure business logic -- no Telegram imports, no rendering. A batch is minted
once and never edited; an admin mints many, one type at a time.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.power_pass import PowerPassType, format_code
from powerbank.db.models import PowerPassCard, PowerPassCounter, User
from powerbank.services.batches import clean_batch_count as clean_batch_count


async def reserve_codes(session: AsyncSession, card_type: PowerPassType, count: int) -> range:
    """Atomically reserve `count` consecutive counter values for `card_type`.

    One UPDATE ... RETURNING takes a row-level lock in both SQLite and
    Postgres, so two admins minting the same type at once never receive
    overlapping ranges -- no SELECT-then-UPDATE race to guard against.
    """
    stmt = (
        update(PowerPassCounter)
        .where(PowerPassCounter.card_type == card_type)
        .values(next_value=PowerPassCounter.next_value + count)
        .returning(PowerPassCounter.next_value)
    )
    new_next = (await session.execute(stmt)).scalar_one()
    return range(new_next - count, new_next)


async def issue_batch(
    session: AsyncSession, admin: User, card_type: PowerPassType, count: int
) -> list[PowerPassCard]:
    """Mint `count` new power-pass cards of `card_type`, tagged with `admin`."""
    numbers = await reserve_codes(session, card_type, count)
    batch = [
        PowerPassCard(created_by_id=admin.id, card_type=card_type, code=format_code(card_type, n))
        for n in numbers
    ]
    session.add_all(batch)
    await session.flush()
    return batch


async def last_codes(session: AsyncSession) -> dict[PowerPassType, str | None]:
    """The most recently minted code of each type, `None` if never minted.

    Reads straight off `PowerPassCounter.next_value` (the *next* number to
    hand out) rather than counting rows, so it reflects the full lineage --
    including the codes issued by hand before this table existed, which the
    seed migration folded into the starting counter values.
    """
    result = await session.execute(select(PowerPassCounter.card_type, PowerPassCounter.next_value))
    next_values = dict(result.all())
    return {
        card_type: (
            format_code(card_type, n - 1) if (n := next_values.get(card_type, 1)) > 1 else None
        )
        for card_type in PowerPassType
    }
