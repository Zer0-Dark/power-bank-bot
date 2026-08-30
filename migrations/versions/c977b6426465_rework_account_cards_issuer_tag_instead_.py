"""rework account cards: issuer tag instead of owner

A card is no longer one-per-user and owned by whoever ran the flow. It is a
standalone record tagged with `created_by_id` -- the employee who issued it --
and an employee issues many. The old `user_id` (unique, one card per user) is
replaced.

Backfill: every pre-existing card is attributed to its own former owner, i.e.
`created_by_id = user_id`. That is the only defensible reading of the old data.

Revision ID: c977b6426465
Revises: 8c35e4f3106d
Create Date: 2026-08-30 18:12:59.792882
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c977b6426465"
down_revision: str | None = "8c35e4f3106d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add the issuer FK: nullable, indexed, SET NULL so removing an employee
    #    keeps the cards they issued as an audit record.
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_by_id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                nullable=True,
            )
        )
        batch_op.create_index(batch_op.f("ix_cards_created_by_id"), ["created_by_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_cards_created_by_id_users"),
            "users",
            ["created_by_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 2. Backfill before the source column goes away.
    op.execute("UPDATE cards SET created_by_id = user_id")

    # 3. Drop the 1:1 link. Explicit drops are for Postgres; on SQLite the batch
    #    recreate omits the column and its constraints anyway.
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_constraint("uq_cards_user_id", type_="unique")
        batch_op.drop_constraint("fk_cards_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")


def downgrade() -> None:
    # Lossy: once any employee has issued more than one card, UNIQUE(user_id)
    # cannot be restored, so surplus rows are dropped (earliest id per user
    # kept) and orphans (SET NULL issuer) are removed.
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                nullable=True,
            )
        )

    op.execute("UPDATE cards SET user_id = created_by_id")
    op.execute("DELETE FROM cards WHERE user_id IS NULL")
    op.execute("DELETE FROM cards WHERE id NOT IN (SELECT MIN(id) FROM cards GROUP BY user_id)")

    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint(batch_op.f("uq_cards_user_id"), ["user_id"])
        batch_op.create_foreign_key(
            batch_op.f("fk_cards_user_id_users"),
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_constraint(batch_op.f("fk_cards_created_by_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_cards_created_by_id"))
        batch_op.drop_column("created_by_id")
