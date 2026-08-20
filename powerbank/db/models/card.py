"""The account card: the four values printed onto the template.

One card per user. The bank number is allocated by us, not typed by the user,
so it is unique and sequential like a real account number.
"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powerbank.db.base import Base, IntPKMixin, TimestampMixin

BANK_NUMBER_DIGITS = 8


class Card(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "cards"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="card")  # noqa: F821

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
        return f"<Card user={self.user_id} no={self.formatted_number}>"
