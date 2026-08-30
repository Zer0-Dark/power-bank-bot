"""Account cards: validating the typed values, issuing, and looking them up.

Pure business logic -- no Telegram imports, no rendering. A card is issued once
and never edited; an employee issues many.
"""

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from powerbank.core.exceptions import UserFacingError
from powerbank.core.roles import Role
from powerbank.db.models import Card, User

MAX_NAME_LENGTH = 40
MAX_USERNAME_LENGTH = 24
BANK_NUMBER_DIGITS = 8

# Arabic-Indic digits are what an Arabic keyboard produces by default.
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


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


def _normalize_bank_number(raw: str) -> int:
    """Arabic-Indic -> ASCII, drop leading zeros, validate. Raises on bad input.

    Accepts a number with or without leading zeros -- `76` and `00000076` are
    the same account, and requiring the padding would just be a trap.
    """
    text = " ".join((raw or "").split()).translate(_ARABIC_INDIC)

    if not text.isdigit():
        raise UserFacingError("الرقم البنكي يجب أن يتكوّن من أرقام فقط.")
    if len(text.lstrip("0")) > BANK_NUMBER_DIGITS:
        raise UserFacingError(f"الرقم البنكي طويل جداً (الحد {BANK_NUMBER_DIGITS} أرقام).")

    number = int(text)
    if number <= 0:
        raise UserFacingError("الرقم البنكي يجب أن يكون أكبر من صفر.")
    return number


async def clean_bank_number(session: AsyncSession, raw: str) -> int:
    """Validate a typed bank number and check no card already holds it."""
    number = _normalize_bank_number(raw)
    taken = await session.scalar(select(Card.id).where(Card.bank_number == number))
    if taken is not None:
        raise UserFacingError("هذا الرقم البنكي مستخدم بالفعل. اختر رقماً آخر.")
    return number


async def issue_card(session: AsyncSession, employee: User, details: CardDetails) -> Card:
    """Insert a standalone card tagged with the employee who issued it."""
    card = Card(
        created_by_id=employee.id,
        real_name=details.real_name,
        facebook_name=details.facebook_name,
        bank_number=details.bank_number,
        display_username=details.display_username,
    )
    session.add(card)

    try:
        await session.flush()
    except IntegrityError as exc:
        # The uniqueness check above can lose a race with a concurrent issue;
        # the constraint on bank_number is the real guarantee.
        raise UserFacingError("هذا الرقم البنكي مستخدم بالفعل. اختر رقماً آخر.") from exc

    return card


async def list_created_by(session: AsyncSession, employee: User, *, limit: int = 20) -> list[Card]:
    """This employee's issued cards, newest first.

    `created_at` is a 1-second CURRENT_TIMESTAMP, so a bulk issuing session ties;
    `id` is the monotonic tie-break.
    """
    result = await session.scalars(
        select(Card)
        .where(Card.created_by_id == employee.id)
        .order_by(Card.created_at.desc(), Card.id.desc())
        .limit(limit)
    )
    return list(result)


async def count_created_by(session: AsyncSession, employee: User) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(Card).where(Card.created_by_id == employee.id)
        )
        or 0
    )


async def issue_counts(session: AsyncSession) -> list[tuple[User, int]]:
    """(member, cards issued) for every member, highest first.

    Outer join so a member who has issued nothing still appears with 0.
    """
    total = func.count(Card.id)
    result = await session.execute(
        select(User, total)
        .outerjoin(Card, Card.created_by_id == User.id)
        .where(User.role.in_((Role.SUPER_ADMIN, Role.ADMIN, Role.USER)))
        .group_by(User.id)
        .order_by(total.desc(), User.id)
    )
    return [(user, count) for user, count in result.all()]


async def find_card(session: AsyncSession, query: str) -> Card | None:
    """All-digits -> exact bank number. Otherwise -> partial name match."""
    text = (query or "").strip()
    if not text:
        return None

    digits = text.translate(_ARABIC_INDIC)
    if digits.isdigit():
        try:
            number = _normalize_bank_number(digits)
        except UserFacingError:
            return None
        return await session.scalar(select(Card).where(Card.bank_number == number))

    like = f"%{text}%"
    return await session.scalar(
        select(Card)
        .where(or_(Card.real_name.ilike(like), Card.facebook_name.ilike(like)))
        .order_by(Card.created_at.desc(), Card.id.desc())
        .limit(1)
    )
