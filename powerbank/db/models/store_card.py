"""Store cards: pre-generated codes minted in batches, with no owner.

`StoreCardCounter` is the source of truth for "the next code to mint" --
exactly one row per card type, seeded by migration from the last codes issued
by hand before this table existed. `StoreCard` is the audit trail of what has
actually been issued. Mirrors `models.coin` exactly.
"""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powerbank.core.store_cards import StoreCardType
from powerbank.db.base import Base, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from powerbank.db.models.user import User

CODE_LENGTH = 24


def _type_enum(name: str) -> Enum:
    # native_enum=False + create_constraint=True: a CHECK-backed string, not a
    # native ENUM -- identical behaviour on SQLite and Postgres. See
    # `PowerPassCounter.card_type` for the same pattern.
    return Enum(
        StoreCardType,
        native_enum=False,
        length=16,
        validate_strings=True,
        create_constraint=True,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
    )


class StoreCardCounter(Base):
    """The next counter value to mint for each store card type.

    `reserve_codes` in the service layer is the only writer -- a single
    UPDATE ... RETURNING advances it atomically.
    """

    __tablename__ = "store_card_counters"

    card_type: Mapped[StoreCardType] = mapped_column(
        _type_enum("store_card_counter_type_enum"), primary_key=True
    )
    next_value: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=False
    )


class StoreCard(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "store_cards"

    # SET NULL, not CASCADE: removing an admin must not erase the cards they
    # minted -- they are an audit record. See `PowerPassCard.created_by_id`.
    created_by_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_by: Mapped["User | None"] = relationship(back_populates="issued_store_cards")

    card_type: Mapped[StoreCardType] = mapped_column(
        _type_enum("store_card_type_enum"), nullable=False, index=True
    )

    code: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True, nullable=False)

    def __repr__(self) -> str:
        return f"<StoreCard id={self.id} type={self.card_type} code={self.code}>"
