"""Coin notes: reserving codes and minting a batch.

Pure business logic -- no Telegram imports, no rendering. A batch is minted
once and never edited; an admin mints many, one denomination at a time.
Mirrors `services.power_pass` exactly; batch-size validation is shared from
there since it carries no coin-specific logic.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.audit import AuditAction
from powerbank.core.coins import CoinType, format_code
from powerbank.db.models import CoinCard, CoinCounter, User
from powerbank.services import audit


async def reserve_codes(session: AsyncSession, coin_type: CoinType, count: int) -> range:
    """Atomically reserve `count` consecutive counter values for `coin_type`.

    One UPDATE ... RETURNING takes a row-level lock in both SQLite and
    Postgres, so two admins minting the same denomination at once never
    receive overlapping ranges -- no SELECT-then-UPDATE race to guard against.
    """
    stmt = (
        update(CoinCounter)
        .where(CoinCounter.coin_type == coin_type)
        .values(next_value=CoinCounter.next_value + count)
        .returning(CoinCounter.next_value)
    )
    new_next = (await session.execute(stmt)).scalar_one()
    return range(new_next - count, new_next)


async def issue_batch(
    session: AsyncSession, admin: User, coin_type: CoinType, count: int
) -> list[CoinCard]:
    """Mint `count` new coin notes of `coin_type`, tagged with `admin`."""
    numbers = await reserve_codes(session, coin_type, count)
    batch = [
        CoinCard(created_by_id=admin.id, coin_type=coin_type, code=format_code(coin_type, n))
        for n in numbers
    ]
    session.add_all(batch)
    await session.flush()
    audit.record_batch(session, AuditAction.COIN_BATCH, admin, coin_type.value, batch)
    return batch


async def last_codes(session: AsyncSession) -> dict[CoinType, str | None]:
    """The most recently minted code of each denomination, `None` if never minted.

    Reads straight off `CoinCounter.next_value` (the *next* number to hand
    out) rather than counting rows, so it reflects the full lineage --
    including the codes issued by hand before this table existed, which the
    seed migration folded into the starting counter values.
    """
    result = await session.execute(select(CoinCounter.coin_type, CoinCounter.next_value))
    next_values = dict(result.all())
    return {
        coin_type: (
            format_code(coin_type, n - 1) if (n := next_values.get(coin_type, 1)) > 1 else None
        )
        for coin_type in CoinType
    }
