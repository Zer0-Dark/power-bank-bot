"""add store cards

Two tables: `store_card_counters` (one row per type, "next code to mint") and
`store_cards` (the audit trail of what has actually been minted). Mirrors
`7c2f6e9a1b4d_add_coin_cards.py` exactly.

The counters are seeded from the last codes already issued by hand, over
Telegram, before this system existed -- every type gave a *last used* code,
so every counter starts one past it.

Revision ID: 5b8d3e1f7a2c
Revises: 7c2f6e9a1b4d
Create Date: 2026-09-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b8d3e1f7a2c"
down_revision: str | None = "7c2f6e9a1b4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES = (
    "'visit_24','visit_48','visit_72','transfer_gold','transfer_silver',"
    "'join_ranked','join_unranked'"
)

# card_type -> next counter value to mint.
_SEED_NEXT_VALUE = {
    "visit_24": 761,  # last used: 0C0P0B0240760
    "visit_48": 301,  # last used: 0C0P0B0480300
    "visit_72": 1280,  # last used: 0C0P0B0721279
    "transfer_gold": 151,  # last used: 00C0P0B011011100150
    "transfer_silver": 601,  # last used: 00C0P0B02202200600
    "join_ranked": 205,  # last used: 00CENTRAL0P0B00204
    "join_unranked": 2001,  # last used: 00CENTRAL0P0B02000
}


def upgrade() -> None:
    op.create_table(
        "store_card_counters",
        sa.Column("card_type", sa.String(length=16), nullable=False),
        sa.Column(
            "next_value", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False
        ),
        sa.CheckConstraint(
            f"card_type IN ({_TYPES})",
            name=op.f("ck_store_card_counters_store_card_counter_type_enum"),
        ),
        sa.PrimaryKeyConstraint("card_type", name=op.f("pk_store_card_counters")),
    )

    op.create_table(
        "store_cards",
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
            f"card_type IN ({_TYPES})",
            name=op.f("ck_store_cards_store_card_type_enum"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_store_cards_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_cards")),
    )
    with op.batch_alter_table("store_cards", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_store_cards_created_by_id"), ["created_by_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_store_cards_card_type"), ["card_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_store_cards_code"), ["code"], unique=True)

    counters = sa.table(
        "store_card_counters",
        sa.column("card_type", sa.String),
        sa.column("next_value", sa.BigInteger),
    )
    op.bulk_insert(
        counters,
        [{"card_type": t, "next_value": v} for t, v in _SEED_NEXT_VALUE.items()],
    )


def downgrade() -> None:
    with op.batch_alter_table("store_cards", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_store_cards_code"))
        batch_op.drop_index(batch_op.f("ix_store_cards_card_type"))
        batch_op.drop_index(batch_op.f("ix_store_cards_created_by_id"))
    op.drop_table("store_cards")
    op.drop_table("store_card_counters")
