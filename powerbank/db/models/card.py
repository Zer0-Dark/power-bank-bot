"""The account card: the four values printed onto the template.

A card is a standalone, immutable record. A bank employee runs the issuing flow
once per person they are making a card for, so many cards can share the same
`created_by_id` and a card is never edited after it is generated. The bank
number is typed by the employee and is unique across every card.
"""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powerbank.db.base import Base, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from powerbank.db.models.user import User

BANK_NUMBER_DIGITS = 8


class Card(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "cards"

    # The employee who ran the issuing flow. SET NULL, not CASCADE: removing an
    # employee must not erase the cards they issued -- they are an audit record.
    created_by_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_by: Mapped["User | None"] = relationship(back_populates="issued_cards")

    # Stored as an integer and zero-padded for display: sequencing and the
    # uniqueness guarantee both belong to the number, not to its formatting.
    bank_number: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        unique=True,
        index=True,
        nullable=False,
    )

    real_name: Mapped[str] = mapped_column(String(64), nullable=False)
    facebook_name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_username: Mapped[str] = mapped_column(String(32), nullable=False)

    @property
    def formatted_number(self) -> str:
        return str(self.bank_number).zfill(BANK_NUMBER_DIGITS)

    def as_values(self) -> dict[str, str]:
        """The payload the renderer draws onto the template."""
        return {
            "real_name": self.real_name,
            "facebook_name": self.facebook_name,
            "bank_number": self.formatted_number,
            "username": self.display_username,
        }

    def __repr__(self) -> str:
        return f"<Card id={self.id} by={self.created_by_id} no={self.formatted_number}>"
