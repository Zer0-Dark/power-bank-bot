"""add audit log

One append-only table, `audit_log`, written by the service layer in the same
transaction as each action.

It is backfilled from what the database already knows, so the history does not
start empty on deploy day:

- every member's current role grant (who granted it, when), and every removal
  that is still the person's latest role change;
- every account card, from `cards.created_by_id` / `created_at`;
- every power-pass, coin and store-card batch -- rows minted together share
  one `created_at` (one INSERT, one transaction), so grouping by admin + type +
  timestamp recovers the batches exactly.

Backfilled lines carry ``"backfilled": true`` in `details`. What the database
never stored (earlier role changes, card lookups, denied attempts) cannot be
recovered and starts being recorded from this revision on.

Revision ID: a3c9f2d4b6e1
Revises: 5b8d3e1f7a2c
Create Date: 2026-09-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c9f2d4b6e1"
down_revision: str | None = "5b8d3e1f7a2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS = (
    "'member_added','role_changed','member_removed','super_admin_seeded','card_issued',"
    "'card_viewed','power_pass_batch','coin_batch','store_card_batch','access_denied'"
)

_ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", _ID, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("actor_id", _ID, nullable=True),
        sa.Column("target_id", _ID, nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(f"action IN ({_ACTIONS})", name=op.f("ck_audit_log_audit_action_enum")),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_log_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["users.id"],
            name=op.f("fk_audit_log_target_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_log_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_log_actor_id"), ["actor_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_log_target_id"), ["target_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_log_action"), ["action"], unique=False)

    _backfill()


def _backfill() -> None:
    conn = op.get_bind()
    rows: list[dict] = []

    def add(action, created_at, actor_id=None, target_id=None, **details) -> None:
        if created_at is None:
            return
        rows.append(
            {
                "created_at": created_at,
                "actor_id": actor_id,
                "target_id": target_id,
                "action": action,
                "details": {**details, "backfilled": True},
            }
        )

    users = sa.table(
        "users",
        sa.column("id", _ID),
        sa.column("role", sa.String),
        sa.column("granted_by_id", _ID),
        sa.column("role_granted_at", sa.DateTime(timezone=True)),
    )
    for u in conn.execute(sa.select(users).where(users.c.role_granted_at.is_not(None))):
        if u.role == "none":
            if u.granted_by_id is not None:
                add("member_removed", u.role_granted_at, u.granted_by_id, u.id)
        elif u.role == "super_admin" and u.granted_by_id is None:
            add("super_admin_seeded", u.role_granted_at, None, u.id)
        else:
            add("member_added", u.role_granted_at, u.granted_by_id, u.id, role=u.role)

    cards = sa.table(
        "cards",
        sa.column("id", _ID),
        sa.column("created_by_id", _ID),
        sa.column("card_type", sa.String),
        sa.column("bank_number", _ID),
        sa.column("real_name", sa.String),
        sa.column("display_username", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for c in conn.execute(sa.select(cards).order_by(cards.c.id)):
        add(
            "card_issued",
            c.created_at,
            c.created_by_id,
            card_id=c.id,
            card_type=c.card_type,
            bank_number=str(c.bank_number).zfill(8),
            real_name=c.real_name,
            username=c.display_username,
        )

    for table_name, type_col, action in (
        ("power_pass_cards", "card_type", "power_pass_batch"),
        ("coin_cards", "coin_type", "coin_batch"),
        ("store_cards", "card_type", "store_card_batch"),
    ):
        t = sa.table(
            table_name,
            sa.column("created_by_id", _ID),
            sa.column(type_col, sa.String),
            sa.column("code", sa.String),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        kind = t.c[type_col]
        batches = conn.execute(
            sa.select(
                t.c.created_by_id,
                kind,
                t.c.created_at,
                sa.func.count().label("n"),
                sa.func.min(t.c.code).label("first"),
                sa.func.max(t.c.code).label("last"),
            ).group_by(t.c.created_by_id, kind, t.c.created_at)
        )
        for b in batches:
            add(
                action,
                b.created_at,
                b.created_by_id,
                type=b[1],
                count=b.n,
                first=b.first,
                last=b.last,
            )

    if rows:
        rows.sort(key=lambda r: r["created_at"])
        log = sa.table(
            "audit_log",
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("actor_id", _ID),
            sa.column("target_id", _ID),
            sa.column("action", sa.String),
            sa.column("details", sa.JSON),
        )
        op.bulk_insert(log, rows)


def downgrade() -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_log_action"))
        batch_op.drop_index(batch_op.f("ix_audit_log_target_id"))
        batch_op.drop_index(batch_op.f("ix_audit_log_actor_id"))
        batch_op.drop_index(batch_op.f("ix_audit_log_created_at"))
    op.drop_table("audit_log")
