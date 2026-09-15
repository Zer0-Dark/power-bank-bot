"""Coin notes: pre-generated codes with no owner, one design per denomination.

Same shape as `power_pass` -- a fixed per-type prefix plus a zero-padded
counter, minted in batches straight off a database counter. Unlike
power-pass, the prefix here is not a short tag but the note's own printed
serial stem (e.g. ``050050`` for the 500 note), so every code is simply
``prefix + counter`` with no extra padding tricks.
"""

from enum import StrEnum


class CoinType(StrEnum):
    """A coin note design, one per denomination."""

    C500 = "500"
    C1000 = "1000"
    C2000 = "2000"
    C5000 = "5000"
    C10000 = "10000"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS: dict[CoinType, str] = {
    CoinType.C500: "عملة 500",
    CoinType.C1000: "عملة 1.000",
    CoinType.C2000: "عملة 2.000",
    CoinType.C5000: "عملة 5.000",
    CoinType.C10000: "عملة 10.000",
}

# The fixed serial stem printed on each note, straight off the samples --
# not derived by a formula, just the value Mary assigned per denomination.
_PREFIX: dict[CoinType, str] = {
    CoinType.C500: "050050",
    CoinType.C1000: "010010",
    CoinType.C2000: "020022",
    CoinType.C5000: "050055",
    CoinType.C10000: "0100123",
}

_COUNTER_DIGITS = 6


def format_code(coin_type: CoinType, n: int) -> str:
    """The printed code for the `n`-th note of this type (1-based, no gaps).

    ``prefix + counter``, e.g. ``050050000151`` for the 151st 500 note.
    """
    return f"{_PREFIX[coin_type]}{str(n).zfill(_COUNTER_DIGITS)}"
