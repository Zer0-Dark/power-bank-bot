"""add roles and access tracking

Revision ID: 92976cac98dd
Revises: de4b68c6d081
Create Date: 2026-08-19 16:09:58.941122
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "92976cac98dd"
down_revision: str | None = "de4b68c6d081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `role` is added as a plain VARCHAR first. Batch mode rebuilds the table and
    # copies rows with INSERT..SELECT, and the source table has no `role` column
    # -- so a CHECK constraint applied here would see NULL and fail. Add the
    # column, backfill it, then constrain it.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(16), server_default="none", nullable=False))
        batch_op.add_column(
            sa.Column(
                "granted_by_id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("role_granted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("denied_attempts", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("last_denied_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_role"), ["role"], unique=False)
        batch_op.create_index(batch_op.f("ix_users_username"), ["username"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_users_granted_by_id_users"),
            "users",
            ["granted_by_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Existing users predate the access system: nobody is grandfathered in.
    op.execute("UPDATE users SET role = 'none' WHERE role IS NULL")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "role_enum", "role IN ('none', 'user', 'admin', 'super_admin')"
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("role_enum", type_="check")
        batch_op.drop_constraint(batch_op.f("fk_users_granted_by_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_users_username"))
        batch_op.drop_index(batch_op.f("ix_users_role"))
        batch_op.drop_column("last_denied_at")
        batch_op.drop_column("denied_attempts")
        batch_op.drop_column("role_granted_at")
        batch_op.drop_column("granted_by_id")
        batch_op.drop_column("role")
