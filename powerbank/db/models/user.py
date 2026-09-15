"""Every Telegram user the bot has ever seen.

A row here does NOT imply access -- `role == Role.NONE` means "we have seen
this person, they are not a member". Keeping non-members lets admins search by
username or id when adding someone, and gives us a record of who tried to get
in.

Deliberately holds no balance. Money lives in accounts + the ledger (Phase 2)
so it can never be mutated by accident from here.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powerbank.core.roles import Role
from powerbank.db.base import Base, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from powerbank.db.models.card import Card
    from powerbank.db.models.coin import CoinCard
    from powerbank.db.models.power_pass import PowerPassCard


class User(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Telegram's user id. BigInteger: these already exceed 32-bit range.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)

    username: Mapped[str | None] = mapped_column(String(32), index=True)
    first_name: Mapped[str | None] = mapped_column(String(64))
    language_code: Mapped[str | None] = mapped_column(String(8))

    # native_enum=False stores VARCHAR + CHECK rather than a Postgres ENUM type,
    # which behaves identically on SQLite and avoids ENUM migration pain.
    # create_constraint=True is not the default -- without it the CHECK is never
    # emitted, and a bad role could reach the database from a raw UPDATE.
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            native_enum=False,
            length=16,
            validate_strings=True,
            create_constraint=True,
            name="role_enum",
            # SQLAlchemy stores enum NAMES by default ('NONE'); we want the
            # lowercase values, which is what server_default writes too.
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=Role.NONE,
        server_default=Role.NONE.value,
        nullable=False,
        index=True,
    )

    # Who granted the current role, and when. Null for env-seeded super admins.
    granted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    granted_by: Mapped["User | None"] = relationship(remote_side="User.id")
    role_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Cards this user has issued. No cascade: the FK is ON DELETE SET NULL so a
    # removed employee's cards survive as an audit record.
    issued_cards: Mapped[list["Card"]] = relationship(
        back_populates="created_by",
        order_by="Card.created_at.desc()",
        passive_deletes=True,
    )

    # Same audit-record reasoning as `issued_cards`, for power-pass batches.
    issued_power_pass_cards: Mapped[list["PowerPassCard"]] = relationship(
        back_populates="created_by",
        order_by="PowerPassCard.created_at.desc()",
        passive_deletes=True,
    )

    # Same audit-record reasoning as `issued_cards`, for coin batches.
    issued_coin_cards: Mapped[list["CoinCard"]] = relationship(
        back_populates="created_by",
        order_by="CoinCard.created_at.desc()",
        passive_deletes=True,
    )

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Access attempts by non-members, so admins can see who is knocking.
    denied_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    last_denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def has_access(self) -> bool:
        return self.role.is_member and not self.is_banned

    @property
    def display(self) -> str:
        """Human-readable handle for admin listings."""
        if self.username:
            return f"@{self.username}"
        return self.first_name or str(self.telegram_id)

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} role={self.role} @{self.username}>"
