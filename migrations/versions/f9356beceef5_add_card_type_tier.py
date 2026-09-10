"""add card_type tier

Cards now come in six designs (bronze .. diamond). ``card_type`` records which
one was rendered. Every pre-existing card is the original design, so the column
is added NOT NULL with a server default of ``diamond`` -- that backfills the
existing rows -- and the CHECK is applied afterwards, mirroring how ``role`` was
added to ``users`` (batch mode copies rows before the constraint would see the
new column otherwise).

Revision ID: f9356beceef5
Revises: c977b6426465
Create Date: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9356beceef5"
down_revision: str | None = "c977b6426465"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECK = "card_type IN ('bronze', 'silver', 'gold', 'royal', 'elite', 'diamond')"


def upgrade() -> None:
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("card_type", sa.String(16), server_default="diamond", nullable=False)
        )
        batch_op.create_index(batch_op.f("ix_cards_card_type"), ["card_type"], unique=False)

    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.create_check_constraint("card_type_enum", _CHECK)


def downgrade() -> None:
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_constraint("card_type_enum", type_="check")
        batch_op.drop_index(batch_op.f("ix_cards_card_type"))
        batch_op.drop_column("card_type")
