"""Store cards: reserving codes and minting a batch.

Pure business logic -- no Telegram imports, no rendering. A batch is minted
once and never edited; a super admin mints many, one type at a time. Mirrors
`services.coins` exactly.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.store_cards import StoreCardType, format_code
from powerbank.db.models import StoreCard, StoreCardCounter, User


async def reserve_codes(session: AsyncSession, card_type: StoreCardType, count: int) -> range:
    """Atomically reserve `count` consecutive counter values for `card_type`.

    One UPDATE ... RETURNING takes a row-level lock, so two admins minting the
    same type at once never receive overlapping ranges.
    """
    stmt = (
        update(StoreCardCounter)
        .where(StoreCardCounter.card_type == card_type)
        .values(next_value=StoreCardCounter.next_value + count)
        .returning(StoreCardCounter.next_value)
    )
    new_next = (await session.execute(stmt)).scalar_one()
    return range(new_next - count, new_next)


async def issue_batch(
    session: AsyncSession, admin: User, card_type: StoreCardType, count: int
) -> list[StoreCard]:
    """Mint `count` new store cards of `card_type`, tagged with `admin`."""
    numbers = await reserve_codes(session, card_type, count)
    batch = [
        StoreCard(created_by_id=admin.id, card_type=card_type, code=format_code(card_type, n))
        for n in numbers
    ]
    session.add_all(batch)
    await session.flush()
    return batch


async def last_codes(session: AsyncSession) -> dict[StoreCardType, str | None]:
    """The most recently minted code of each type, `None` if never minted.

    Reads straight off `StoreCardCounter.next_value` rather than counting rows,
    so it reflects the codes issued by hand before this table existed too.
    """
    result = await session.execute(select(StoreCardCounter.card_type, StoreCardCounter.next_value))
    next_values = dict(result.all())
    return {
        card_type: (
            format_code(card_type, n - 1) if (n := next_values.get(card_type, 1)) > 1 else None
        )
        for card_type in StoreCardType
    }
