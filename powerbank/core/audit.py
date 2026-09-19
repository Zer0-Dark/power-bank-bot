"""The actions the audit log records.

Pure domain -- no database, no aiogram. The enum *value* is what lands in the
database, so it stays ASCII; the Arabic label and icon are display-only.
"""

from enum import StrEnum


class AuditAction(StrEnum):
    """Something a person (or the bot itself) did that is worth a history line."""

    MEMBER_ADDED = "member_added"
    ROLE_CHANGED = "role_changed"
    MEMBER_REMOVED = "member_removed"
    SUPER_ADMIN_SEEDED = "super_admin_seeded"
    CARD_ISSUED = "card_issued"
    CARD_VIEWED = "card_viewed"
    POWER_PASS_BATCH = "power_pass_batch"
    COIN_BATCH = "coin_batch"
    STORE_CARD_BATCH = "store_card_batch"
    ACCESS_DENIED = "access_denied"

    @property
    def icon(self) -> str:
        return _ICONS[self]


_ICONS: dict[AuditAction, str] = {
    AuditAction.MEMBER_ADDED: "➕",
    AuditAction.ROLE_CHANGED: "🔁",
    AuditAction.MEMBER_REMOVED: "➖",
    AuditAction.SUPER_ADMIN_SEEDED: "👑",
    AuditAction.CARD_ISSUED: "🪪",
    AuditAction.CARD_VIEWED: "🔎",
    AuditAction.POWER_PASS_BATCH: "🎫",
    AuditAction.COIN_BATCH: "🪙",
    AuditAction.STORE_CARD_BATCH: "🛒",
    AuditAction.ACCESS_DENIED: "🚪",
}
