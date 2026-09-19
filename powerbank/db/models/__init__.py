"""Every model must be imported here so Alembic autogenerate can see it."""

from powerbank.db.base import Base
from powerbank.db.models.audit import AuditEvent
from powerbank.db.models.card import Card
from powerbank.db.models.coin import CoinCard, CoinCounter
from powerbank.db.models.power_pass import PowerPassCard, PowerPassCounter
from powerbank.db.models.store_card import StoreCard, StoreCardCounter
from powerbank.db.models.user import User

__all__ = [
    "AuditEvent",
    "Base",
    "Card",
    "CoinCard",
    "CoinCounter",
    "PowerPassCard",
    "PowerPassCounter",
    "StoreCard",
    "StoreCardCounter",
    "User",
]
