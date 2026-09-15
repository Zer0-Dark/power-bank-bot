"""add coin cards

Two tables: `coin_counters` (one row per denomination, "next code to mint")
and `coin_cards` (the audit trail of what has actually been minted). Mirrors
`31a0cf89e2a2_add_power_pass_cards.py` exactly.

The counters are seeded from the last codes already issued by hand, over
Telegram, before this system existed -- all five denominations gave a *last
used* code, so every counter starts one past it.

Revision ID: 7c2f6e9a1b4d
Revises: 31a0cf89e2a2
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c2f6e9a1b4d"
down_revision: str | None = "31a0cf89e2a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# coin_type -> next counter value to mint.
_SEED_NEXT_VALUE = {
    "500": 151,  # last used: 050050000150
    "1000": 1210,  # last used: 010010001209
    "2000": 801,  # last used: 020022000800
    "5000": 1551,  # last used: 050055001550
    "10000": 201,  # last used: 0100123000200
}


def upgrade() -> None:
    op.create_table(
        "coin_counters",
        sa.Column("coin_type", sa.String(length=16), nullable=False),
        sa.Column(
            "next_value", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.CheckConstraint(
            "coin_type IN ('500','1000','2000','5000','10000')",
            name=op.f("ck_coin_counters_coin_counter_type_enum"),
        ),
        sa.PrimaryKeyConstraint("coin_type", name=op.f("pk_coin_counters")),
    )

    op.create_table(
        "coin_cards",
        sa.Column(
            "created_by_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("coin_type", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "coin_type IN ('500','1000','2000','5000','10000')",
            name=op.f("ck_coin_cards_coin_card_type_enum"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_coin_cards_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coin_cards")),
    )
    with op.batch_alter_table("coin_cards", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_coin_cards_created_by_id"), ["created_by_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_coin_cards_coin_type"), ["coin_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_coin_cards_code"), ["code"], unique=True)

    counters = sa.table(
        "coin_counters",
        sa.column("coin_type", sa.String),
        sa.column("next_value", sa.BigInteger),
    )
    op.bulk_insert(
        counters,
        [{"coin_type": t, "next_value": v} for t, v in _SEED_NEXT_VALUE.items()],
    )


def downgrade() -> None:
    with op.batch_alter_table("coin_cards", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_coin_cards_code"))
        batch_op.drop_index(batch_op.f("ix_coin_cards_coin_type"))
        batch_op.drop_index(batch_op.f("ix_coin_cards_created_by_id"))
    op.drop_table("coin_cards")
    op.drop_table("coin_counters")
