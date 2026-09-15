"""Power-pass cards: pre-generated codes minted in batches, with no owner.

`PowerPassCounter` is the source of truth for "the next code to mint" --
exactly one row per type, seeded by migration from the last codes issued by
hand before this table existed. `PowerPassCard` is the audit trail of what
has actually been issued; a batch insert tags every row with the admin who
ran the flow, same as `Card.created_by_id`.
"""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powerbank.core.power_pass import PowerPassType
from powerbank.db.base import Base, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from powerbank.db.models.user import User

CODE_LENGTH = 24


def _type_enum(name: str) -> Enum:
    # native_enum=False + create_constraint=True: a CHECK-backed string, not a
    # native ENUM -- identical behaviour on SQLite and Postgres. See
    # `Card.card_type` for the same pattern.
    return Enum(
        PowerPassType,
        native_enum=False,
        length=16,
        validate_strings=True,
        create_constraint=True,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
    )


class PowerPassCounter(Base):
    """The next counter value to mint for each power-pass type.

    `reserve_codes` in the service layer is the only writer -- a single
    UPDATE ... RETURNING advances it atomically, so two admins minting at the
    same time never receive overlapping ranges.
    """

    __tablename__ = "power_pass_counters"

    card_type: Mapped[PowerPassType] = mapped_column(
        _type_enum("power_pass_counter_type_enum"), primary_key=True
    )
    next_value: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=False
    )


class PowerPassCard(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "power_pass_cards"

    # SET NULL, not CASCADE: removing an admin must not erase the passes they
    # minted -- they are an audit record. See `Card.created_by_id`.
    created_by_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_by: Mapped["User | None"] = relationship(back_populates="issued_power_pass_cards")

    card_type: Mapped[PowerPassType] = mapped_column(
        _type_enum("power_pass_card_type_enum"), nullable=False, index=True
    )

    code: Mapped[str] = mapped_column(String(CODE_LENGTH), unique=True, index=True, nullable=False)

    def __repr__(self) -> str:
        return f"<PowerPassCard id={self.id} type={self.card_type} code={self.code}>"
