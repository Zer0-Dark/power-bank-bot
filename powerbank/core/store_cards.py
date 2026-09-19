"""Store cards: pre-generated codes with no owner, one design per card type.

Same shape as `coins` -- a fixed per-type prefix plus a zero-padded counter,
minted in batches straight off a database counter. The enum *value* is what
lands in the database, so it stays ASCII; the Arabic label is display-only.
Each type has one template + layout under ``assets/`` keyed by the value
(``visit_24`` -> ``layouts/store-cards/visit_24.json``).
"""

from enum import StrEnum


class StoreCardType(StrEnum):
    """A store card design: a timed visit, a team transfer, or a join card."""

    VISIT_24 = "visit_24"
    VISIT_48 = "visit_48"
    VISIT_72 = "visit_72"
    TRANSFER_GOLD = "transfer_gold"
    TRANSFER_SILVER = "transfer_silver"
    JOIN_RANKED = "join_ranked"
    JOIN_UNRANKED = "join_unranked"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS: dict[StoreCardType, str] = {
    StoreCardType.VISIT_24: "بطاقة زيارة 24 ساعة",
    StoreCardType.VISIT_48: "بطاقة زيارة 48 ساعة",
    StoreCardType.VISIT_72: "بطاقة زيارة 72 ساعة",
    StoreCardType.TRANSFER_GOLD: "بطاقة نقل ذهبية",
    StoreCardType.TRANSFER_SILVER: "بطاقة نقل فضية",
    StoreCardType.JOIN_RANKED: "بطاقة انضمام (فترة التصنيف)",
    StoreCardType.JOIN_UNRANKED: "بطاقة انضمام (بدون تصنيف)",
}

# (fixed stem, counter digits) per type, straight off the last codes Mary
# issued by hand -- e.g. ``0C0P0B0240760`` is stem ``0C0P0B024`` + ``0760``.
# Note the two join types share one stem and differ only by counter range.
_FORMAT: dict[StoreCardType, tuple[str, int]] = {
    StoreCardType.VISIT_24: ("0C0P0B024", 4),
    StoreCardType.VISIT_48: ("0C0P0B048", 4),
    StoreCardType.VISIT_72: ("0C0P0B072", 4),
    StoreCardType.TRANSFER_GOLD: ("00C0P0B0110111", 5),
    StoreCardType.TRANSFER_SILVER: ("00C0P0B022022", 5),
    StoreCardType.JOIN_RANKED: ("00CENTRAL0P0B", 5),
    StoreCardType.JOIN_UNRANKED: ("00CENTRAL0P0B", 5),
}


def format_code(card_type: StoreCardType, n: int) -> str:
    """The printed code for the `n`-th card of this type (1-based, no gaps).

    ``stem + zero-padded counter``, e.g. ``0C0P0B0240761`` for the 761st
    24-hour visit card.
    """
    stem, digits = _FORMAT[card_type]
    return f"{stem}{str(n).zfill(digits)}"
