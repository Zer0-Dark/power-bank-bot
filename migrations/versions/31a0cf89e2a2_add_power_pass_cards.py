"""add power-pass cards

Two tables: `power_pass_counters` (one row per type, "next code to mint") and
`power_pass_cards` (the audit trail of what has actually been minted).

The counters are seeded from the last codes already issued by hand, over
Telegram, before this system existed -- `join`/`gold_72`/`silver_72` give a
*last used* code, so their counter starts one past it; the rest give a
*starting* code, so their counter starts right at it.

Revision ID: 31a0cf89e2a2
Revises: f9356beceef5
Create Date: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "31a0cf89e2a2"
down_revision: str | None = "f9356beceef5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# card_type -> next counter value to mint.
_SEED_NEXT_VALUE = {
    "join": 101,  # last used: ...000100
    "gold_72": 101,  # last used: ...72G0100
    "silver_72": 2,  # last used: ...72S0001
    "gold_48": 1,  # starting point: ...48G0001
    "silver_48": 1,  # starting point: ...48S0001
    "gold_24": 1,  # starting point: ...24G0001
    "silver_24": 1,  # starting point: ...24S0001
}


def upgrade() -> None:
    op.create_table(
        "power_pass_counters",
        sa.Column("card_type", sa.String(length=16), nullable=False),
        sa.Column(
            "next_value", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.CheckConstraint(
            "card_type IN ('join','gold_72','gold_48','gold_24',"
            "'silver_72','silver_48','silver_24')",
            name=op.f("ck_power_pass_counters_power_pass_counter_type_enum"),
        ),
        sa.PrimaryKeyConstraint("card_type", name=op.f("pk_power_pass_counters")),
    )

    op.create_table(
        "power_pass_cards",
        sa.Column(
            "created_by_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("card_type", sa.String(length=16), nullable=False),
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
            "card_type IN ('join','gold_72','gold_48','gold_24',"
            "'silver_72','silver_48','silver_24')",
            name=op.f("ck_power_pass_cards_power_pass_card_type_enum"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_power_pass_cards_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_power_pass_cards")),
    )
    with op.batch_alter_table("power_pass_cards", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_power_pass_cards_created_by_id"), ["created_by_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_power_pass_cards_card_type"), ["card_type"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_power_pass_cards_code"), ["code"], unique=True)

    counters = sa.table(
        "power_pass_counters",
        sa.column("card_type", sa.String),
        sa.column("next_value", sa.BigInteger),
    )
    op.bulk_insert(
        counters,
        [{"card_type": t, "next_value": v} for t, v in _SEED_NEXT_VALUE.items()],
    )


def downgrade() -> None:
    with op.batch_alter_table("power_pass_cards", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_power_pass_cards_code"))
        batch_op.drop_index(batch_op.f("ix_power_pass_cards_card_type"))
        batch_op.drop_index(batch_op.f("ix_power_pass_cards_created_by_id"))
    op.drop_table("power_pass_cards")
    op.drop_table("power_pass_counters")
