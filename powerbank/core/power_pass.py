"""Power-pass cards: pre-generated codes with no owner.

Pure domain logic -- no database, no aiogram, no rendering. Unlike an account
`Card`, nobody types a name onto one of these: an admin mints a batch straight
from a per-type counter, and the printed code is the entire payload. The enum
*value* is what lands in the database, so it stays ASCII; the Arabic label is
display-only. Each type has one template + layout under ``assets/`` keyed by
the value (``gold_72`` -> ``layouts/power-pass/gold_72.json``).
"""

from enum import StrEnum


class PowerPassType(StrEnum):
    """A power-pass design: the join card, or a timed visit pass."""

    JOIN = "join"
    GOLD_72 = "gold_72"
    GOLD_48 = "gold_48"
    GOLD_24 = "gold_24"
    SILVER_72 = "silver_72"
    SILVER_48 = "silver_48"
    SILVER_24 = "silver_24"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS: dict[PowerPassType, str] = {
    PowerPassType.JOIN: "بطاقة الانضمام",
    PowerPassType.GOLD_72: "زيارة ذهبية 72 ساعة",
    PowerPassType.GOLD_48: "زيارة ذهبية 48 ساعة",
    PowerPassType.GOLD_24: "زيارة ذهبية 24 ساعة",
    PowerPassType.SILVER_72: "زيارة فضية 72 ساعة",
    PowerPassType.SILVER_48: "زيارة فضية 48 ساعة",
    PowerPassType.SILVER_24: "زيارة فضية 24 ساعة",
}

# The 2-3 char tag baked into every code right after the fixed prefix, and how
# many digits the trailing counter is padded to. The join card carries no
# tier/duration, so it has no tag -- a longer counter and an extra leading
# zero take up the same width instead, keeping every code 18 characters long,
# matching the ones already issued by hand before this system existed.
_TAG: dict[PowerPassType, str] = {
    PowerPassType.JOIN: "",
    PowerPassType.GOLD_72: "72G",
    PowerPassType.GOLD_48: "48G",
    PowerPassType.GOLD_24: "24G",
    PowerPassType.SILVER_72: "72S",
    PowerPassType.SILVER_48: "48S",
    PowerPassType.SILVER_24: "24S",
}

_PREFIX = "CPB0P0PASS"
_COUNTER_DIGITS = 4
_JOIN_COUNTER_DIGITS = 6
_JOIN_PAD = "00"
_TAGGED_PAD = "0"


def format_code(card_type: PowerPassType, n: int) -> str:
    """The printed code for the `n`-th card of this type (1-based, no gaps).

    ``pad + prefix + tag + counter``, e.g. ``0CPB0P0PASS72G0101`` for the
    101st gold 72h pass, or ``00CPB0P0PASS000101`` for the 101st join card.
    """
    if card_type is PowerPassType.JOIN:
        return f"{_JOIN_PAD}{_PREFIX}{str(n).zfill(_JOIN_COUNTER_DIGITS)}"
    return f"{_TAGGED_PAD}{_PREFIX}{_TAG[card_type]}{str(n).zfill(_COUNTER_DIGITS)}"
