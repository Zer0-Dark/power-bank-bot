"""Card tiers: the visual designs a member can choose to issue.

Pure domain logic -- no database, no aiogram, no rendering. The enum *value* is
what lands in the database and in callback payloads, so it stays ASCII; the
Arabic name is display-only. Each tier has one template + layout under
``assets/`` keyed by the value (``bronze`` -> ``layouts/bronze.json``).
"""

from enum import StrEnum


class CardType(StrEnum):
    """An account-card design. Ordered from the lowest tier to the highest."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    ROYAL = "royal"
    ELITE = "elite"
    DIAMOND = "diamond"

    @property
    def label(self) -> str:
        return _LABELS[self]


# The only card design before tiers existed -- every pre-existing row is one of
# these, so it is the backfill value and the server default.
DEFAULT_CARD_TYPE = CardType.DIAMOND

# Displayed to users, so Arabic. Definite article included to match the artwork.
_LABELS: dict[CardType, str] = {
    CardType.BRONZE: "البرونزي",
    CardType.SILVER: "الفضي",
    CardType.GOLD: "الذهبي",
    CardType.ROYAL: "الملكي",
    CardType.ELITE: "النخبة",
    CardType.DIAMOND: "الماسي",
}
