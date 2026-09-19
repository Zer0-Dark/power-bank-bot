"""The audit log: one row per thing someone did, append-only.

Rows are written by the service layer in the *same* transaction as the action
they describe, so an action and its history line commit or roll back together
-- there is no way to do something without it being recorded.

`details` is a small JSON dict of whatever that action needs to be described
later (a card number, a batch's first and last code, the old and new role).
Values are stored raw (enum values, not Arabic labels) so the wording can
change without rewriting history.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from powerbank.core.audit import AuditAction
from powerbank.db.base import Base, IntPKMixin

if TYPE_CHECKING:
    from powerbank.db.models.user import User

_USER_FK = BigInteger().with_variant(Integer, "sqlite")


class AuditEvent(IntPKMixin, Base):
    __tablename__ = "audit_log"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Who did it. NULL for the bot itself (e.g. seeding super admins at
    # startup). SET NULL, not CASCADE: history must outlive the people in it.
    actor_id: Mapped[int | None] = mapped_column(
        _USER_FK, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])

    # Who it was done to, for membership actions. NULL when there is no person
    # on the receiving end (a card batch, a card lookup).
    target_id: Mapped[int | None] = mapped_column(
        _USER_FK, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    target: Mapped["User | None"] = relationship(foreign_keys=[target_id])

    action: Mapped[AuditAction] = mapped_column(
        Enum(
            AuditAction,
            native_enum=False,
            length=32,
            validate_strings=True,
            create_constraint=True,
            name="audit_action_enum",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        index=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} action={self.action} actor={self.actor_id}>"
