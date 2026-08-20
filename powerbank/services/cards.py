"""Account cards: the four values printed on a member's card.

Pure business logic -- no Telegram imports, no rendering.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.exceptions import UserFacingError
from powerbank.db.models import Card, User

MAX_NAME_LENGTH = 40
MAX_USERNAME_LENGTH = 24
BANK_NUMBER_DIGITS = 8


@dataclass(frozen=True, slots=True)
class CardDetails:
    """Validated input for a card."""

    real_name: str
    facebook_name: str
    bank_number: int
    display_username: str


def clean_name(raw: str, label: str, limit: int = MAX_NAME_LENGTH) -> str:
    """Normalise and validate one typed value.

    Collapses whitespace: users paste names with stray newlines and doubled
    spaces, and those would render as gaps on the card.
    """
    value = " ".join((raw or "").split())
    if not value:
        raise UserFacingError(f"{label} لا يمكن أن يكون فارغاً.")
    if len(value) > limit:
        raise UserFacingError(f"{label} طويل جداً (الحد {limit} حرفاً).")
    return value


async def get_for_user(session: AsyncSession, user: User) -> Card | None:
    return await session.scalar(select(Card).where(Card.user_id == user.id))


async def clean_bank_number(session: AsyncSession, raw: str, owner: User) -> int:
    """Validate a typed bank number and check nobody else holds it.

    Accepts it with or without leading zeros -- `76` and `00000076` are the same
    account, and requiring the padding would just be a trap.
    """
    text = " ".join((raw or "").split())
    # Arabic-Indic digits are what an Arabic keyboard produces by default.
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))

    if not text.isdigit():
        raise UserFacingError("الرقم البنكي يجب أن يتكوّن من أرقام فقط.")
    if len(text.lstrip("0")) > BANK_NUMBER_DIGITS:
        raise UserFacingError(f"الرقم البنكي طويل جداً (الحد {BANK_NUMBER_DIGITS} أرقام).")

    number = int(text)
    if number <= 0:
        raise UserFacingError("الرقم البنكي يجب أن يكون أكبر من صفر.")

    holder = await session.scalar(select(Card).where(Card.bank_number == number))
    if holder is not None and holder.user_id != owner.id:
        raise UserFacingError("هذا الرقم البنكي مستخدم بالفعل. اختر رقماً آخر.")

    return number


async def save_card(session: AsyncSession, user: User, details: CardDetails) -> Card:
    """Create or update this user's card."""
    card = await get_for_user(session, user)

    if card is None:
        card = Card(user_id=user.id)
        session.add(card)

    card.real_name = details.real_name
    card.facebook_name = details.facebook_name
    card.bank_number = details.bank_number
    card.display_username = details.display_username

    try:
        await session.flush()
    except IntegrityError as exc:
        # The uniqueness check above can lose a race with a simultaneous
        # registration; the constraint is the real guarantee.
        raise UserFacingError(
            "هذا الرقم البنكي مستخدم بالفعل. اختر رقماً آخر."
        ) from exc

    return card
