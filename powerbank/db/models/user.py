"""The player record.

Deliberately holds no balance. Money lives in accounts + the ledger (Phase 2)
so it can never be mutated by accident from here.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from powerbank.db.base import Base, IntPKMixin, TimestampMixin


class User(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Telegram's user id. BigInteger: these already exceed 32-bit range.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    username: Mapped[str | None] = mapped_column(String(32))
    first_name: Mapped[str | None] = mapped_column(String(64))
    language_code: Mapped[str | None] = mapped_column(String(8))

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} @{self.username}>"
